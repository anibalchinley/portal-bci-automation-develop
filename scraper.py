import gc
import os
import time
import json
import re
import io
import datetime
import traceback
import pdfplumber
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium import webdriver # Reemplazamos UC por el webdriver estándar
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
import pandas as pd
import base64
from twocaptcha import TwoCaptcha
from selenium_stealth import stealth

def detectar_contexto_actual(driver):
    """
    Detecta el contexto actual (BCI o Zenit) basado en el logo visible.
    Espera hasta 10 segundos para que aparezca uno de los logos.

    Args:
        driver: Instancia de Selenium WebDriver.

    Returns:
        str: "BCI", "ZENIT", o "DESCONOCIDO" si no se encuentra ninguno.
    """
    try:
        # Espera explícita para cualquiera de los dos logos
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "img.bci, img.zenit"))
        )
        
        # Verificar logo BCI
        logo_bci = driver.find_elements(By.CSS_SELECTOR, "img.bci")
        if logo_bci and logo_bci[0].is_displayed():
            print("Contexto detectado: BCI")
            return "BCI"
            
        # Verificar logo Zenit
        logo_zenit = driver.find_elements(By.CSS_SELECTOR, "img.zenit")
        if logo_zenit and logo_zenit[0].is_displayed():
            print("Contexto detectado: ZENIT")
            return "ZENIT"
            
        return "DESCONOCIDO"
    except TimeoutException:
        print("Error de Timeout: No se encontró el logo de BCI ni de Zenit a tiempo.")
        return "DESCONOCIDO"
    except Exception as e:
        print(f"Error inesperado en detectar_contexto_actual: {e}")
        return "DESCONOCIDO"

def verificar_contexto_bci(driver):
    """
    Verifica si el contexto actual es BCI Seguros utilizando la nueva función de detección.
    
    Args:
        driver: Instancia de Selenium WebDriver
        
    Returns:
        bool: True si el contexto es BCI Seguros, False en caso contrario
    """
    return detectar_contexto_actual(driver) == "BCI"

def buscar_opcion_contexto(driver, texto_buscar):
    """
    Busca una opción específica en el menú de contexto.
    
    Args:
        driver: Instancia de Selenium WebDriver
        texto_buscar: Texto a buscar en las opciones del menú
        
    Returns:
        WebElement: Elemento encontrado o None si no se encuentra
    """
    try:
        # Intentar con XPath que incluya el texto completo
        xpath = f"//*[contains(translate(., 'ÁÉÍÓÚ', 'AEIOU'), '{texto_buscar.upper()}')]"
        elementos = driver.find_elements(By.XPATH, xpath)
        
        # Filtrar solo elementos visibles y clickeables
        for elemento in elementos:
            try:
                if elemento.is_displayed() and elemento.is_enabled():
                    return elemento
            except:
                continue
                
        # Si no se encontró, buscar en menús desplegables
        menus = driver.find_elements(By.XPATH, "//*[contains(@class, 'dropdown-menu') or contains(@class, 'menu-list')]")
        for menu in menus:
            if menu.is_displayed():
                opciones = menu.find_elements(By.XPATH, ".//*[contains(translate(., 'ÁÉÍÓÚ', 'AEIOU'), '" + texto_buscar.upper() + "')] ")
                for opcion in opciones:
                    if opcion.is_displayed() and opcion.is_enabled():
                        return opcion
                        
        return None
    except Exception as e:
        print(f"Error en buscar_opcion_contexto: {str(e)}")
        return None

def buscar_primera_opcion_valida(driver):
    """
    Busca la primera opción válida en el menú de contexto.
    
    Args:
        driver: Instancia de Selenium WebDriver
        
    Returns:
        WebElement: Primera opción válida encontrada o None
    """
    try:
        # Buscar en menús desplegables visibles
        menus = driver.find_elements(By.XPATH, "//*[contains(@class, 'dropdown-menu') or contains(@class, 'menu-list')]")
        
        for menu in menus:
            if menu.is_displayed():
                # Buscar cualquier elemento clickeable dentro del menú
                opciones = menu.find_elements(By.XPATH, ".//*[self::a or self::button or self::div[contains(@class, 'item')]]")
                for opcion in opciones:
                    try:
                        if opcion.is_displayed() and opcion.is_enabled() and opcion.text.strip():
                            return opcion
                    except:
                        continue
        
        return None
    except Exception as e:
        print(f"Error en buscar_primera_opcion_valida: {str(e)}")
        return None

def take_screenshot(driver, filename="screenshot.png"):
        """Toma una captura de pantalla y la guarda en el directorio /tmp/screenshots/."""
        screenshot_dir = "/tmp/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        filepath = os.path.join(screenshot_dir, filename)
        try:
            driver.save_screenshot(filepath)
            print(f"DEBUG: Captura de pantalla guardada en {filepath}", flush=True)
        except Exception as e:
            print(f"DEBUG: Error al tomar captura de pantalla {filename}: {e}", flush=True)

def setup_driver():
        """Configura e inicializa el WebDriver estándar de Selenium para Render."""
        print("--- Entrando a setup_driver (MODO ESTÁNDAR DE SELENIUM)...", flush=True)
        
        options = webdriver.ChromeOptions()
        print("1. ChromeOptions inicializado.", flush=True)
        
        # Configurar directorio de descargas en /tmp
        downloads_path = "/tmp/downloads"
        os.makedirs(downloads_path, exist_ok=True)
        
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        
        # Configurar preferencias de descarga
        prefs = {
            "download.default_directory": downloads_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        print("2. Opciones de Chrome (headless, no-sandbox, etc.) añadidas.", flush=True)
        print(f"3. Directorio de descargas configurado: {downloads_path}", flush=True)

        # En el entorno de Render, el chromedriver que instala el Dockerfile está en el PATH del sistema.
        # Selenium lo encuentra automáticamente, por lo que no es necesario un Service object.
        print("3. Inicializando webdriver.Chrome...", flush=True)
        
        try:
            driver = webdriver.Chrome(options=options)
            
            # Configurar timeouts más largos para Render
            driver.set_page_load_timeout(180)  # 3 minutos
            driver.implicitly_wait(30)  # 30 segundos
            
            print("4. ¡ÉXITO! WebDriver de Selenium (Modo Estándar) inicializado.", flush=True)
            print("5. Timeouts configurados para entorno de producción.", flush=True)
        except Exception as e:
            print(f"Error al inicializar webdriver.Chrome: {e}", flush=True)
            print("Esto puede indicar un problema con el chromedriver en el PATH del servidor.", flush=True)
            return None

        print("6. Aplicando parches de sigilo con selenium-stealth...", flush=True)
        stealth(driver,
                languages=["es-ES", "es"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                )
        print("7. Parches de sigilo aplicados.", flush=True)
        
        return driver

def login_to_bci(driver, user, password, api_key_2captcha):
        """Navega a la página de BCI, resuelve el reCAPTCHA y realiza el login."""
        url = "https://webproveedores.bciseguros.cl/login"
        try:
            print(f"Navegando a: {url}", flush=True)
            driver.get(url)
            print(f"DEBUG: URL actual: {driver.current_url}", flush=True)
            
            user_selector = 'input[formcontrolname="username"]';
            pass_selector = 'input[formcontrolname="password"]';
            button_selector = 'button.boton.bg-azul';
            
            print("Esperando a que los campos de usuario y contraseña sean visibles.", flush=True)
            email_input = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, user_selector)))
            email_input.send_keys(user)
            print("DEBUG: Usuario ingresado.", flush=True)
            
            password_input = driver.find_element(By.CSS_SELECTOR, pass_selector)
            password_input.send_keys(password)
            print("DEBUG: Contraseña ingresada. Credenciales completas.", flush=True)

            print("Iniciando lógica para reCAPTCHA v3...", flush=True)
            page_source = driver.page_source
            
            match = re.search(r'https://www.google.com/recaptcha/api.js\?render=([^&]+)', page_source)
            
            if not match:
                print("Error: No se pudo encontrar el sitekey de reCAPTCHA v3 en el código fuente.", flush=True)
                take_screenshot(driver, "03_sitekey_not_found.png")
                return False
                
            sitekey = match.group(1)
            print(f"Sitekey de reCAPTCHA v3 encontrado: {sitekey}", flush=True)

            try:
                solver = TwoCaptcha(api_key_2captcha)
                print("Enviando reCAPTCHA v3 a 2Captcha... (esto puede tardar)", flush=True)
                result = solver.recaptcha(
                    sitekey=sitekey,
                    url=url,
                    version='v3',
                    action='login',
                    score=0.7
                )

                if result and result.get('code'):
                    token = result['code']
                    print("reCAPTCHA v3 resuelto. Inyectando token.", flush=True)
                    recaptcha_element_selector = '[name="g-recaptcha-response"]';
                    js_inyectar_token = f"document.querySelector('{recaptcha_element_selector}').value = arguments[0];"

                    try:
                        print(f"INTENTO A: Esperando que el elemento '{recaptcha_element_selector}' exista.", flush=True)
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, recaptcha_element_selector))
                        )
                        print("INTENTO A: Éxito. El elemento reCAPTCHA fue encontrado en el DOM.", flush=True)
                        driver.execute_script(js_inyectar_token, token)
                        print("Token inyectado en el elemento existente.", flush=True)

                    except TimeoutException:
                        print("INTENTO A: Falló. El elemento reCAPTCHA no se encontró.", flush=True)
                        print("INTENTO B: Creando el elemento dinámicamente.", flush=True)
                        js_crear_e_inyectar = f"""
                        var newTextarea = document.createElement('textarea');
                        newTextarea.name = 'g-recaptcha-response';
                        newTextarea.style.display = 'none';
                        document.body.appendChild(newTextarea);
                        document.querySelector('{recaptcha_element_selector}').value = arguments[0];
                        """
                        driver.execute_script(js_crear_e_inyectar, token)
                        print("INTENTO B: Éxito. Elemento creado y token inyectado.", flush=True)
                else:
                    print(f"Error: No se pudo obtener una solución de 2Captcha. Respuesta: {result}", flush=True)
                    return False

            except Exception as e:
                print(f"Error durante el proceso de resolución de CAPTCHA: {e}", flush=True)
                return False

            print("Haciendo clic en el botón de login...", flush=True)
            login_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, button_selector)))
            login_button.click()
            print("DEBUG: Clic en botón de login realizado.", flush=True)
            
            print("Esperando redirección a 'busqueda-avanzada'...", flush=True)
            WebDriverWait(driver, 15).until(EC.url_contains('busqueda-avanzada'))
            print(f"Login exitoso. Nueva URL: {driver.current_url}", flush=True)
            
            # Verificar que la sesión esté realmente activa
            try:
                if check_login_status(driver):
                    print("Sesión verificada correctamente.", flush=True)
                    # Añadido: Pequeña pausa y manejo de popups post-login para robustez
                    print("Pausa post-login y manejo de popups inicial.", flush=True)
                    time.sleep(2)
                    manejar_posibles_popups(driver)
                    return True
                else:
                    print("No se pudo verificar la sesión.", flush=True)
                    return False
            except Exception as e:
                print(f"Error al verificar el estado de login: {e}", flush=True)
                return False
                
        except Exception as e:
            print(f"Error durante el proceso de login: {e}", flush=True)
            print(f"Traceback completo del login:\n{traceback.format_exc()}", flush=True)
            take_screenshot(driver, "09_login_exception.png")
            return False


def check_login_status(driver):
    """
    Verifica si el driver sigue logueado buscando un elemento clave en la página.
    
    Args:
        driver: Instancia de Selenium WebDriver
        
    Returns:
        bool: True si la sesión está activa, False en caso contrario
    """
    print("\n--- Verificando estado de login ---", flush=True)
    try:
        # Buscar el elemento 'Calendario' que confirma sesión activa
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Calendario')]" ))
        )
        print("Elemento 'Calendario' encontrado. Sesión activa.", flush=True)
        return True
    except TimeoutException:
        print("Elemento 'Calendario' no encontrado. Sesión perdida.", flush=True)
        return False
    except Exception as e:
        print(f"Error al verificar el estado de login: {e}", flush=True)
        take_screenshot(driver, "error_check_login_status.png")
        return False

def esperar_pagina_cargada(driver, timeout=30):
    """
    Espera a que la página se cargue completamente y que los loaders desaparezcan.
    """
    print("--- Esperando carga completa de la página y desaparición de loaders ---", flush=True)
    try:
        # 1. Esperar a que el estado del documento sea 'complete'
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        print("Documento cargado.", flush=True)

        # 2. Esperar a que cualquier loader desaparezca
        loader_selector = "div.loader-container, .loader, [role='progressbar']"
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, loader_selector))
        )
        print("Loaders desaparecidos. La página está lista.", flush=True)
        return True
    except TimeoutException:
        print("Timeout esperando la carga de la página o la desaparición de los loaders.", flush=True)
        take_screenshot(driver, "error_carga_pagina.png")
        return False

def manejar_popup_bienvenida(driver, timeout=30):
    """
    Busca y cierra la ventana emergente de bienvenida y espera a que su fondo desaparezca.
    
    Args:
        driver: Instancia de Selenium WebDriver
        timeout: Tiempo máximo de espera en segundos
        
    Returns:
        bool: True si se manejó correctamente, False en caso contrario
    """
    print("\n--- Buscando pop-up de bienvenida ---", flush=True)
    
    try:
        # 1. Esperar a que la página y los loaders estén listos
        if not esperar_pagina_cargada(driver, timeout):
            return False # Si la página no carga, no podemos continuar
        
        # 2. Intentar diferentes selectores para el botón de aceptar
        button_selectors = [
            "//button[contains(., 'Aceptar') or contains(., 'Acepto') or contains(., 'Entendido')]",
            "//div[contains(@class, 'mat-dialog-actions')]//button[contains(., 'Aceptar')]",
            "//button[contains(@class, 'mat-button') and contains(., 'Aceptar')]"
        ]
        
        button_found = False
        for selector in button_selectors:
            try:
                print(f"Intentando con selector: {selector}", flush=True)
                accept_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                driver.execute_script("arguments[0].click();", accept_button)
                print("Botón de aceptar clickeado con éxito.", flush=True)
                button_found = True
                break
            except Exception:
                print(f"No se pudo interactuar con el botón usando {selector}", flush=True)
        
        if not button_found:
            print("No se encontró ningún botón de aceptar visible y clickeable.", flush=True)
            return False
        
        # 3. Esperar a que desaparezcan los backdrops
        backdrop_selectors = [
            "div.cdk-overlay-backdrop",
            ".modal-backdrop",
            ".mat-dialog-backdrop"
        ]
        
        for selector in backdrop_selectors:
            try:
                WebDriverWait(driver, 10).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                print(f"Backdrop '{selector}' desaparecido.", flush=True)
            except:
                print(f"No se encontró el backdrop '{selector}' o ya desapareció.", flush=True)
        
        print("Toda la interfaz está lista para interactuar.", flush=True)
        return True
            
    except Exception as e:
        error_msg = f"Error inesperado en manejar_popup_bienvenida: {str(e)[:200]}"
        print(error_msg, flush=True)
        take_screenshot(driver, "error_popup_bienvenida.png")
        raise Exception(f"Fallo al manejar el pop-up de bienvenida: {str(e)[:200]}")


def manejar_posibles_popups(driver):
    """
    Maneja posibles popups que puedan aparecer durante la navegación.
    Incluye manejo de popups de bienvenida, notificaciones y otros diálogos emergentes.
    """
    try:
        # Primero intentar manejar el popup de bienvenida estándar
        try:
            manejar_popup_bienvenida(driver)
        except Exception as e:
            print(f"No se pudo manejar el popup de bienvenida: {str(e)[:200]}", flush=True)
        
        # Esperar un momento para que cualquier popup se cargue completamente
        time.sleep(2)
        
        # Intentar cerrar cualquier notificación o diálogo emergente
        try:
            # Buscar botones de cierre en diálogos modales
            botones_cierre = driver.find_elements(By.XPATH, 
                "//button[contains(@class, 'close') or contains(@class, 'mat-dialog-close') or @aria-label='Cerrar' or @title='Cerrar']"
            )
            
            for boton in botones_cierre:
                try:
                    if boton.is_displayed() and boton.is_enabled():
                        driver.execute_script("arguments[0].click();", boton)
                        print("Botón de cierre de diálogo encontrado y clickeado.", flush=True)
                        time.sleep(1)  # Esperar a que se cierre la animación
                except:
                    continue
                    
        except Exception as e:
            print(f"Error al intentar cerrar diálogos: {str(e)[:200]}", flush=True)
        
        # Verificar si hay algún overlay o backdrop que bloquee la interacción
        try:
            backdrops = driver.find_elements(By.CSS_SELECTOR, ".cdk-overlay-backdrop, .modal-backdrop, .mat-dialog-backdrop")
            for backdrop in backdrops:
                try:
                    if backdrop.is_displayed():
                        # Intentar hacer clic en una esquina del backdrop para cerrarlo
                        driver.execute_script("arguments[0].click();", backdrop)
                        print("Backdrop encontrado y clickeado.", flush=True)
                        time.sleep(1)
                except:
                    continue
        except Exception as e:
            print(f"Error al manejar backdrops: {str(e)[:200]}", flush=True)
            
    except Exception as e:
        print(f"Error inesperado en manejar_posibles_popups: {str(e)[:200]}", flush=True)
        take_screenshot(driver, "error_manejo_popups.png")
    
    return True


def asegurar_contexto(driver, compania_objetivo, max_retries=2):
    """
    Asegura que el bot esté operando en el contexto deseado (BCI o ZENIT).
    Versión 9.6: Comparación case-insensitive y limpieza de debug logs.

    Args:
        driver: Instancia de Selenium WebDriver.
        compania_objetivo: "BCI" o "ZENIT".
        max_retries: Número máximo de reintentos.

    Returns:
        bool: True si el contexto es o se cambió al objetivo, False en caso contrario.
    """
    print(f"\n--- Asegurando contexto {compania_objetivo.upper()} (v9.6) ---", flush=True)
    
    opciones_menu = {
        "BCI": "BCI Seguros",
        "ZENIT": "Zenit Seguros"
    }
    texto_opcion_menu = opciones_menu.get(compania_objetivo.upper())
    if not texto_opcion_menu:
        print(f"Error: Compañía objetivo '{compania_objetivo}' no es válida.", flush=True)
        return False

    for attempt in range(1, max_retries + 1):
        print(f"Intento {attempt}/{max_retries}...", flush=True)
        
        contexto_actual = detectar_contexto_actual(driver)
        
        if contexto_actual == compania_objetivo.upper():
            print(f"Éxito: El contexto actual ya es {compania_objetivo.upper()}.")
            return True
            
        if contexto_actual == "DESCONOCIDO":
            print("Error: No se pudo determinar el contexto actual. Abortando.", flush=True)
            take_screenshot(driver, f"contexto_desconocido_attempt_{attempt}.png")
            return False

        print(f"Contexto actual es {contexto_actual}. Intentando cambiar a {compania_objetivo.upper()}...")
        
        try:
            # Paso 1: Clic en el botón del menú de usuario con JS
            user_menu_selector = "a#userDropdown"
            user_menu_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, user_menu_selector))
            )
            driver.execute_script("arguments[0].click();", user_menu_button)

            # Paso 2: Esperar a que el panel del menú esté visible
            menu_panel_selector = "div.dropdown-menu.show"
            menu_panel = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, menu_panel_selector))
            )
            print("Panel del menú desplegable está visible.")

            # Paso 3: Iterar y encontrar la opción correcta usando innerHTML (case-insensitive)
            options = menu_panel.find_elements(By.TAG_NAME, "a")
            option_found = False
            for option in options:
                inner_html = option.get_attribute('innerHTML')
                if texto_opcion_menu.lower() in inner_html.lower():
                    print(f"Opción encontrada en innerHTML: '{inner_html.strip()}'. Haciendo clic.")
                    driver.execute_script("arguments[0].click();", option)
                    option_found = True
                    break
            
            if not option_found:
                print(f"Error: No se encontró la opción '{texto_opcion_menu}' en el menú.")
                raise TimeoutException(f"La opción '{texto_opcion_menu}' no fue encontrada en el menú.")

            # Paso 4: Esperar y verificar el cambio
            print("Cambio de contexto solicitado. Esperando carga de página...")
            esperar_pagina_cargada(driver)
            manejar_popup_bienvenida(driver)

            print(f"Esperando la confirmación del cambio a {compania_objetivo.upper()}...")
            WebDriverWait(driver, 20).until(
                lambda d: detectar_contexto_actual(d) == compania_objetivo.upper()
            )
            
            print(f"Éxito: El contexto se cambió a {compania_objetivo.upper()} correctamente.")
            return True

        except TimeoutException as e:
            print(f"Error de Timeout en el intento {attempt}: {e}")
            take_screenshot(driver, f"contexto_timeout_attempt_{attempt}.png")
            if attempt == max_retries:
                print("Se agotaron los reintentos para cambiar de contexto.")
                traceback.print_exc()
                return False
            time.sleep(3)
            
        except Exception as e:
            print(f"Error inesperado en el intento {attempt}: {e}")
            take_screenshot(driver, f"contexto_error_inesperado_attempt_{attempt}.png")
            if attempt == max_retries:
                print("Se agotaron los reintentos debido a errores inesperados.")
                traceback.print_exc()
                return False
            time.sleep(3)

    return False


def extraer_datos_pdf(driver):
    """
    Encuentra el enlace 'VER DENUNCIO', abre el PDF en una nueva pestaña,
    extrae el 'Relato', 'VIN' y 'Número de Asegurado', y luego cierra la pestaña.
    """
    print("--- Iniciando extracción de PDF ---", flush=True)
    pdf_data = {"Relato": None, "VIN": None, "NumeroAsegurado": None}
    original_window = driver.current_window_handle

    try:
        ver_denuncio_link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'VER DENUNCIO')]" ))
        )
        print("Enlace 'VER DENUNCIO' encontrado y clickeado.", flush=True)
        ver_denuncio_link.click()

        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                break
        print(f"Cambiado a la nueva pestaña del PDF: {driver.current_url}", flush=True)

        js_script = """
            var url = window.location.href;
            var response = await fetch(url);
            var blob = await response.blob();
            var reader = new FileReader();
            var promise = new Promise((resolve, reject) => {
                reader.onloadend = () => resolve(reader.result);
                reader.onerror = reject;
            });
            reader.readAsDataURL(blob);
            return promise;
        """
        data_url = driver.execute_script(js_script)
        header, encoded = data_url.split(",", 1)
        pdf_bytes = base64.b64decode(encoded)
        print("Contenido del PDF descargado y decodificado.", flush=True)

        full_text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + "\n"
        
        # --- Expresiones Regulares v4.1 ---
        # Extracción del Relato
        relato_match = re.search(r"RELATO\n([\s\S]*?)(?=\nDATOS VEHÍCULO)", full_text, re.IGNORECASE)
        if relato_match:
            pdf_data["Relato"] = relato_match.group(1).strip()

        # Extracción del VIN
        vin_match = re.search(r"VIN Marca/Modelo/Año Patente\n([A-Z0-9]{17})", full_text)
        if vin_match:
            pdf_data["VIN"] = vin_match.group(1).strip()
            
        # Extracción del N° de Póliza
        asegurado_match = re.search(r"Póliza Ítem del Vehículo en Póliza Deducible Póliza\n(.*?)\s", full_text)
        if asegurado_match:
            pdf_data["NumeroAsegurado"] = asegurado_match.group(1).strip()

        print(f"Datos extraídos del PDF: {pdf_data}", flush=True)

    except TimeoutException:
        print("WARN: No se encontró el enlace 'VER DENUNCIO' o la pestaña del PDF no apareció.", flush=True)
        take_screenshot(driver, "pdf_link_no_encontrado.png")
    except Exception as e:
        print(f"ERROR: Fallo inesperado durante la extracción del PDF: {e}", flush=True)
        traceback.print_exc()
        take_screenshot(driver, "pdf_extraccion_error.png")
    finally:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(original_window)
            print("Pestaña del PDF cerrada. Volviendo a la pestaña original.", flush=True)
    return pdf_data

def safe_extract_text(row, selector):
    """
    Extrae texto de un elemento de manera segura, devolviendo cadena vacía si no existe.

    Args:
        row: Elemento WebElement de la fila
        selector: Selector CSS del elemento a extraer

    Returns:
        str: Texto del elemento o cadena vacía si no existe
    """
    try:
        element = row.find_element(By.CSS_SELECTOR, selector)
        return element.text.strip() if element.text else ''
    except NoSuchElementException:
        return ''



def sondear_siniestros_asignados(driver, compania):
    """
    Orquesta el proceso de scraping en la pestaña 'Asignados'.
    v4.5: Añade el parámetro compania para etiquetar los datos.
    """
    print(f"\n--- Iniciando sondeo de Siniestros Asignados para {compania.upper()} ---", flush=True)
    processed_siniestros = set()
    try:
        # Navegación a la pestaña 'Asignados'
        print("Navegando a la pestaña 'Asignados'", flush=True)
        WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Asignados')]" ))).click()
        esperar_pagina_cargada(driver)

        page_num = 1
        while True:
            print(f"\nRecolectando datos de tabla en página {page_num}...", flush=True)
            row_selector = "//tr[contains(@class, 'mat-row')]"
            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, row_selector)))
                rows = driver.find_elements(By.XPATH, row_selector)
            except TimeoutException:
                rows = []
            if not rows:
                print("No se encontraron más filas de 'Asignados' en esta página. Finalizando recolección.", flush=True)
                break
            print(f"Encontradas {len(rows)} filas en la página {page_num}.", flush=True)

            # Extraer todos los datos de cada fila
            for row in rows:
                row_data = {
                    'Compania': compania,
                    'FechaAsignacion': safe_extract_text(row, "td.mat-column-FechaAsignacion"),
                    'NumeroSiniestro': safe_extract_text(row, "td.mat-column-NumeroSiniestro"),
                    'EstadoContacto': safe_extract_text(row, "td.mat-column-EstadoContacto"),
                    'Patente': safe_extract_text(row, "td.mat-column-Patente"),
                    'NombreAsegurado': safe_extract_text(row, "td.mat-column-NombreAsegurado"),
                    'RutAsegurado': safe_extract_text(row, "td.mat-column-RutAsegurado"),
                    'CorreoAsegurado': safe_extract_text(row, "td.mat-column-EmailAsegurado"),
                    'TelefonoAsegurado': safe_extract_text(row, "td.mat-column-TelefonoAsegurado"),
                    'Marca': safe_extract_text(row, "td.mat-column-Marca"),
                    'Modelo': safe_extract_text(row, "td.mat-column-Modelo"),
                    'TipoDanio': safe_extract_text(row, "td.mat-column-TipoDanio"),
                    'FechaEstimadaIngreso': safe_extract_text(row, "td.mat-column-FechaEstimadaIngreso")
                }
                yield row_data
                processed_siniestros.add(row_data['NumeroSiniestro'])

            print(f"Datos de {len(rows)} filas guardados.", flush=True)

            # Paginación
            try:
                next_button_selector = "button.mat-paginator-navigation-next:not([disabled])"
                next_button = driver.find_element(By.CSS_SELECTOR, next_button_selector)
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_button)
                esperar_pagina_cargada(driver)
                page_num += 1

                # Verificar si se encontraron nuevas filas después de la paginación
                time.sleep(2)  # Dar tiempo a que se cargue la nueva página
                row_selector = "//tr[contains(@class, 'mat-row')]"
                try:
                    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, row_selector)))
                    rows_after_pagination = driver.find_elements(By.XPATH, row_selector)
                except TimeoutException:
                    rows_after_pagination = []

                if not rows_after_pagination:
                    print("No se encontraron filas en la nueva página. Fin de la recolección.", flush=True)
                    break

                # Verificar si hay al menos una fila nueva única
                new_unique_found = False
                for row in rows_after_pagination[:5]:  # Revisar las primeras 5 filas
                    numero_siniestro = safe_extract_text(row, "td.mat-column-NumeroSiniestro")
                    if numero_siniestro and numero_siniestro not in processed_siniestros:
                        new_unique_found = True
                        break

                if not new_unique_found:
                    print("No se encontraron filas nuevas únicas en la página. Fin de la recolección.", flush=True)
                    break

            except (NoSuchElementException, TimeoutException):
                print("No hay más páginas o el botón de siguiente está deshabilitado. Fin de la recolección.", flush=True)
                break
            
            gc.collect()

    except Exception as e:
        print(f"Error crítico durante la recolección de la tabla: {e}", flush=True)
        traceback.print_exc()
        take_screenshot(driver, "error_critico_recoleccion_tabla.png")
    
    print(f"\n--- Proceso de sondeo completado. ---", flush=True)

def sondear_siniestros_liquidacion(driver, compania):
    """
    Orquesta el proceso de descarga y procesamiento de Excel en la pestaña 'Analisis de Liquidación'.
    v5.1: Implementación corregida con validaciones, limpieza de datos y estructura consistente.
    """
    print(f"\n--- Iniciando sondeo de Siniestros Analisis de Liquidación para {compania.upper()} (Excel) ---", flush=True)

    processed_siniestros = []

    try:
        # PASO 1: Navegar a la pestaña 'Analisis de Liquidación'
        print("Navegando a la pestaña 'Analisis de Liquidación'", flush=True)
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Analisis de Liquidación')]"))
        ).click()
        esperar_pagina_cargada(driver)

        # PASO 2: Verificar que hay datos para descargar
        try:
            # Buscar el número de registros en la pestaña
            tab_element = driver.find_element(By.XPATH, "//a[contains(text(), 'Analisis de Liquidación')]")
            tab_text = tab_element.text

            # Extraer número de registros (ej: "Analisis de Liquidación (18)")
            import re
            match = re.search(r'\((\d+)\)', tab_text)
            expected_records = int(match.group(1)) if match else 0

            print(f"Registros esperados según pestaña: {expected_records}", flush=True)

            if expected_records == 0:
                print("No hay registros en Análisis de Liquidación. Saltando descarga.", flush=True)
                return

        except Exception as e:
            print(f"No se pudo determinar número de registros: {e}", flush=True)
            expected_records = None

        # PASO 3: Preparar descarga
        print("Buscando y clickeando el botón de Excel...", flush=True)

        # Configurar directorio de descargas para Render
        downloads_dir = "/tmp/downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        print(f"Directorio de descargas configurado: {downloads_dir}", flush=True)
        
        # Limpiar descargas anteriores
        excel_files_before = [f for f in os.listdir(downloads_dir) if f.endswith('.xlsx')]

        # Buscar y hacer clic en el botón de Excel
        excel_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//img[contains(@src, 'excel-icon')]]"))
        )
        driver.execute_script("arguments[0].click();", excel_button)
        print("Descarga iniciada...", flush=True)

        # PASO 4: Esperar y validar descarga
        max_wait_time = 60  # 60 segundos máximo para Render
        wait_time = 0
        downloaded_file = None

        while wait_time < max_wait_time:
            time.sleep(2)  # Esperar un poco más en cada iteración
            wait_time += 2

            try:
                # Buscar nuevos archivos Excel
                if os.path.exists(downloads_dir):
                    excel_files_after = [f for f in os.listdir(downloads_dir) if f.endswith('.xlsx')]
                    new_files = [f for f in excel_files_after if f not in excel_files_before]

                    if new_files:
                        potential_file = os.path.join(downloads_dir, new_files[0])
                        # Verificar estabilidad del archivo (tamaño no cambia)
                        if os.path.exists(potential_file):
                            size1 = os.path.getsize(potential_file)
                            time.sleep(2)
                            if os.path.exists(potential_file):
                                size2 = os.path.getsize(potential_file)
                                if size1 == size2 and size1 > 0:
                                    downloaded_file = potential_file
                                    print(f"Archivo descargado y verificado: {new_files[0]} ({size1} bytes)", flush=True)
                                    break
                                else:
                                    print(f"Archivo aún descargando... ({size1} -> {size2} bytes)", flush=True)
            except Exception as e:
                print(f"Error verificando descargas: {e}", flush=True)

            if wait_time % 10 == 0:
                print(f"Esperando descarga... ({wait_time}s)", flush=True)

        if not downloaded_file:
            # Intentar buscar cualquier archivo Excel en el directorio
            try:
                all_excel_files = [f for f in os.listdir(downloads_dir) if f.endswith('.xlsx')]
                if all_excel_files:
                    # Usar el archivo más reciente
                    downloaded_file = os.path.join(downloads_dir, max(all_excel_files, key=lambda f: os.path.getctime(os.path.join(downloads_dir, f))))
                    print(f"Usando archivo Excel más reciente: {os.path.basename(downloaded_file)}", flush=True)
                else:
                    raise Exception(f"No se pudo descargar el archivo Excel en el tiempo esperado. Directorio: {downloads_dir}")
            except Exception as e:
                raise Exception(f"No se pudo descargar el archivo Excel: {e}")

        # PASO 5: Leer y validar archivo Excel
        print("Procesando archivo Excel...", flush=True)

        try:
            # Leer el archivo Excel
            df = pd.read_excel(downloaded_file)

            print(f"Archivo Excel leído: {df.shape[0]} filas, {df.shape[1]} columnas", flush=True)

            # Verificar que tiene las columnas esperadas
            expected_columns = [
                'FECHA INGRESO', 'N° SINIESTRO', 'PATENTE', 'RUT ASEGURADO',
                'MARCA', 'MODELO', 'TIPO DAÑO', 'MOTIVO RECHAZO',
                'VEHICULO INMOVILIZADO INGRESO', 'FECHA RECHAZO'
            ]

            missing_columns = [col for col in expected_columns if col not in df.columns]
            if missing_columns:
                print(f"ADVERTENCIA: Columnas faltantes: {missing_columns}", flush=True)
                print(f"Columnas disponibles: {list(df.columns)}", flush=True)

            # PASO 6: Procesar cada fila del Excel con limpieza de datos
            for index, row in df.iterrows():
                try:
                    # Extraer y validar número de siniestro
                    numero_siniestro = str(row.get('N° SINIESTRO', '')).strip()

                    if not numero_siniestro or numero_siniestro in ['nan', 'NaN', 'None', 'null', '']:
                        print(f"Saltando fila {index}: número de siniestro inválido", flush=True)
                        continue

                    # Verificar duplicados
                    if numero_siniestro in [s['NumeroSiniestro'] for s in processed_siniestros]:
                        print(f"Saltando fila {index}: siniestro duplicado {numero_siniestro}", flush=True)
                        continue

                    # Función para limpiar valores
                    def clean_value(value):
                        if pd.isna(value) or value in ['nan', 'NaN', 'None', 'null', None]:
                            return ''
                        return str(value).strip()

                    # Procesar fecha de ingreso
                    fecha_ingreso = row.get('FECHA INGRESO', '')
                    if pd.notna(fecha_ingreso) and str(fecha_ingreso) != 'nan':
                        # Convertir formato de fecha si es necesario
                        if 'T' in str(fecha_ingreso):
                            fecha_ingreso = str(fecha_ingreso).split('T')[0]
                        else:
                            fecha_ingreso = clean_value(fecha_ingreso)
                    else:
                        fecha_ingreso = ''

                    # Procesar fecha de rechazo
                    fecha_rechazo = row.get('FECHA RECHAZO', '')
                    if pd.notna(fecha_rechazo) and str(fecha_rechazo) != 'nan':
                        if 'T' in str(fecha_rechazo):
                            fecha_rechazo = str(fecha_rechazo).split('T')[0]
                        else:
                            fecha_rechazo = clean_value(fecha_rechazo)
                    else:
                        fecha_rechazo = ''

                    # Crear estructura de datos CONSISTENTE con Asignados
                    row_data = {
                        'Compania': compania,
                        'TipoSeccion': 'Liquidacion',
                        'FechaIngreso': fecha_ingreso,
                        'NumeroSiniestro': numero_siniestro,
                        'Patente': clean_value(row.get('PATENTE', '')),
                        'RutAsegurado': clean_value(row.get('RUT ASEGURADO', '')),
                        'Marca': clean_value(row.get('MARCA', '')),
                        'Modelo': clean_value(row.get('MODELO', '')),
                        'TipoDano': clean_value(row.get('TIPO DAÑO', '')),
                        'MotivoRechazo': clean_value(row.get('MOTIVO RECHAZO', '')),
                        'VehiculoInmovilizadoIngreso': clean_value(row.get('VEHICULO INMOVILIZADO INGRESO', '')),
                        'FechaRechazo': fecha_rechazo,
                        # Campos adicionales para consistencia con Asignados (vacíos para Liquidación)
                        'FechaAsignacion': '',
                        'EstadoContacto': '',
                        'NombreAsegurado': '',
                        'CorreoAsegurado': '',
                        'TelefonoAsegurado': '',
                        'FechaEstimadaIngreso': ''
                    }

                    processed_siniestros.append(row_data)
                    yield row_data

                    print(f"DEBUG: ✅ Procesado siniestro {numero_siniestro} - {row_data['Patente']} - {row_data['Marca']} {row_data['Modelo']}", flush=True)

                except Exception as e:
                    print(f"Error procesando fila {index}: {e}", flush=True)
                    continue

            print(f"Procesamiento completado: {len(processed_siniestros)} siniestros extraídos del Excel", flush=True)

            # Verificar si el número coincide con lo esperado
            if expected_records and len(processed_siniestros) != expected_records:
                print(f"ADVERTENCIA: Se esperaban {expected_records} registros, se procesaron {len(processed_siniestros)}", flush=True)
            else:
                print(f"✅ ÉXITO: Se procesaron exactamente {len(processed_siniestros)} registros como se esperaba", flush=True)

        except Exception as e:
            print(f"Error procesando archivo Excel: {e}", flush=True)
            traceback.print_exc()
            raise

        finally:
            # PASO 7: Limpiar archivo descargado
            try:
                if downloaded_file and os.path.exists(downloaded_file):
                    os.remove(downloaded_file)
                    print("Archivo Excel temporal eliminado", flush=True)
                # Limpiar otros archivos Excel antiguos en el directorio
                for file in os.listdir(downloads_dir):
                    if file.endswith('.xlsx'):
                        file_path = os.path.join(downloads_dir, file)
                        try:
                            os.remove(file_path)
                            print(f"Archivo Excel antiguo eliminado: {file}", flush=True)
                        except Exception as e:
                            print(f"No se pudo eliminar archivo antiguo {file}: {e}", flush=True)
            except Exception as e:
                print(f"No se pudo eliminar archivos temporales: {e}", flush=True)

    except Exception as e:
        print(f"Error crítico durante la descarga/procesamiento de Excel: {e}", flush=True)
        traceback.print_exc()
        take_screenshot(driver, "error_critico_liquidacion_excel.png")

    print(f"\n--- Proceso de sondeo de Analisis de Liquidación (Excel) completado. Total siniestros procesados: {len(processed_siniestros)} ---", flush=True)

def scrape_full_data(driver):
    """
    Orquesta el proceso completo de scraping para todas las compañías definidas.
    """
    print("--- Iniciando proceso de scraping completo ---", flush=True)

    companias = ["BCI", "ZENIT"]

    for compania in companias:
        print(f"\n--- Procesando compañía: {compania.upper()} ---", flush=True)
        if asegurar_contexto(driver, compania):
            # Navegación a Gestión de siniestros
            print("Navegando a Siniestros -> Gestión de siniestros...", flush=True)
            WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Siniestros')]" ))).click()
            esperar_pagina_cargada(driver)
            submenu_container = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div#item-1.show")))
            submenu_container.find_element(By.XPATH, ".//a[contains(., 'Gestión de siniestros')]" ).click()
            esperar_pagina_cargada(driver)
            yield from sondear_siniestros_asignados(driver, compania)
            yield from sondear_siniestros_liquidacion(driver, compania)
        else:
            print(f"ADVERTENCIA: No se pudo asegurar el contexto para {compania.upper()}. Saltando esta compañía.", flush=True)
            take_screenshot(driver, f"error_contexto_{compania.lower()}.png")