import gc
import os
import time
import json
import re
import io
import datetime
import pandas as pd
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
import traceback
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
        
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        download_dir = "/tmp/downloads"
        os.makedirs(download_dir, exist_ok=True)
        print("3. Directorio de descargas configurado en /tmp/downloads.", flush=True)
        options.add_experimental_option("prefs", {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        })
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        print("2. Opciones de Chrome (headless, no-sandbox, etc.) añadidas.", flush=True)

        # En el entorno de Render, el chromedriver que instala el Dockerfile está en el PATH del sistema.
        # Selenium lo encuentra automáticamente, por lo que no es necesario un Service object.
        print("3. Inicializando webdriver.Chrome...", flush=True)
        
        try:
            driver = webdriver.Chrome(options=options)
            print("4. ¡ÉXITO! WebDriver de Selenium (Modo Estándar) inicializado.", flush=True)
        except Exception as e:
            print(f"Error al inicializar webdriver.Chrome: {e}", flush=True)
            print("Esto puede indicar un problema con el chromedriver en el PATH del servidor.", flush=True)
            return None

        print("5. Aplicando parches de sigilo con selenium-stealth...", flush=True)
        stealth(driver,
                languages=["es-ES", "es"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                )
        print("6. Parches de sigilo aplicados.", flush=True)
        
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

def sondear_siniestros_asignados(driver, compania):
    """
    Orquesta el proceso de scraping en la pestaña 'Asignados'.
    v4.5: Añade el parámetro compania para etiquetar los datos.
    """
    print(f"\n--- Iniciando sondeo de Siniestros Asignados para {compania.upper()} ---", flush=True)
    
    try:
        # Navegación inicial
        print("Navegando a Siniestros -> Gestión de siniestros...", flush=True)
        WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Siniestros')]" ))).click()
        esperar_pagina_cargada(driver)
        submenu_container = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div#item-1.show")))
        submenu_container.find_element(By.XPATH, ".//a[contains(., 'Gestión de siniestros')]" ).click()
        esperar_pagina_cargada(driver)
        print("Navegando a la pestaña 'Asignados'", flush=True)
        WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Asignados')]" ))).click()
        esperar_pagina_cargada(driver)

        page_num = 1
        while True:
            print(f"\nRecolectando datos de tabla en página {page_num}...", flush=True)
            row_selector = "//tr[contains(@class, 'mat-row') and .//td[contains(@class, 'mat-column-FechaAsignacion')]]"
            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, row_selector)))
                rows = driver.find_elements(By.XPATH, row_selector)
                print(f"Encontradas {len(rows)} filas en la página {page_num}.", flush=True)

                # Extraer todos los datos de cada fila
                for row in rows:
                    row_data = {
                        'Compania': compania,
                        'FechaAsignacion': row.find_element(By.CSS_SELECTOR, "td.mat-column-FechaAsignacion").text,
                        'NumeroSiniestro': row.find_element(By.CSS_SELECTOR, "td.mat-column-NumeroSiniestro").text,
                        'EstadoContacto': row.find_element(By.CSS_SELECTOR, "td.mat-column-EstadoContacto").text,
                        'Patente': row.find_element(By.CSS_SELECTOR, "td.mat-column-Patente").text,
                        'NombreAsegurado': row.find_element(By.CSS_SELECTOR, "td.mat-column-NombreAsegurado").text,
                        'RutAsegurado': row.find_element(By.CSS_SELECTOR, "td.mat-column-RutAsegurado").text,
                        'CorreoAsegurado': row.find_element(By.CSS_SELECTOR, "td.mat-column-EmailAsegurado").text,
                        'TelefonoAsegurado': row.find_element(By.CSS_SELECTOR, "td.mat-column-TelefonoAsegurado").text,
                        'Marca': row.find_element(By.CSS_SELECTOR, "td.mat-column-Marca").text,
                        'Modelo': row.find_element(By.CSS_SELECTOR, "td.mat-column-Modelo").text,
                        'TipoDanio': row.find_element(By.CSS_SELECTOR, "td.mat-column-TipoDanio").text,
                        'FechaEstimadaIngreso': row.find_element(By.CSS_SELECTOR, "td.mat-column-FechaEstimadaIngreso").text
                    }
                    yield row_data
                
                print(f"Datos de {len(rows)} filas guardados.", flush=True)

            except TimeoutException:
                print("No se encontraron más filas de 'Asignados' en esta página. Finalizando recolección.", flush=True)
                break

            # Paginación
            try:
                # Store the first row's unique identifier before attempting to paginate
                first_row_id_before_pagination = None
                if rows: # Check if there are rows on the current page
                    try:
                        first_row_id_before_pagination = rows[0].find_element(By.CSS_SELECTOR, "td.mat-column-NumeroSiniestro").text
                    except NoSuchElementException:
                        print("WARN: Could not get first row ID for pagination check.", flush=True)

                next_button_selector = "button.mat-paginator-navigation-next:not([disabled])"
                next_button = driver.find_element(By.CSS_SELECTOR, next_button_selector)
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", next_button)
                esperar_pagina_cargada(driver)
                page_num += 1

                # After clicking next, re-evaluate rows on the new page
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, row_selector)))
                rows_after_pagination = driver.find_elements(By.XPATH, row_selector)

                # Check if the content has changed (i.e., we moved to a new page) and if the number of rows is 0
                if first_row_id_before_pagination and rows_after_pagination:
                    first_row_id_after_pagination = rows_after_pagination[0].find_element(By.CSS_SELECTOR, "td.mat-column-NumeroSiniestro").text
                    if first_row_id_before_pagination == first_row_id_after_pagination:
                        print("Detectado bucle de paginación: La primera fila no cambió. Fin de la recolección.", flush=True)
                        break # Break if we are stuck on the same page content
                elif not rows_after_pagination: # If no rows are found on the new page, it's the end
                    print("No se encontraron filas en la nueva página. Fin de la recolección.", flush=True)
                    break

            except (NoSuchElementException, TimeoutException):
                print("No hay más páginas o el botón de siguiente está deshabilitado. Fin de la recolección.", flush=True)
                break
            
            gc.collect()

    except Exception as e:
        print(f"Error crítico durante la recolección de la tabla: {e}", flush=True)
        traceback.print_exc()
        take_screenshot(driver, "error_critico_recoleccion_tabla.png")
    
def sondear_siniestros_liquidacion(driver, compania):
    """
    Orquesta el proceso de descarga y procesamiento de Excel para Análisis de Liquidación.
    """
    print(f"\n--- Iniciando sondeo de Siniestros Liquidación para {compania.upper()} ---", flush=True)

    # Verificar estado actual antes de navegación
    current_url = driver.current_url
    try:

        # Verificar si el submenu está visible
        submenu_visible = False
        submenu_container = None
        try:
            submenu_container = driver.find_element(By.CSS_SELECTOR, "div#item-1.show")
            if submenu_container.is_displayed():
                submenu_visible = True
                # print("DEBUG: Submenu 'div#item-1.show' ya está visible.", flush=True)
        except NoSuchElementException:
            pass
            # print("DEBUG: Submenu 'div#item-1.show' no encontrado.", flush=True)

        # DEBUG: Inspeccionar pestañas disponibles en el submenu
        if submenu_container and submenu_visible:
            try:
                tabs = submenu_container.find_elements(By.TAG_NAME, "a")
                # print("DEBUG: Pestañas disponibles en el submenu:", flush=True)
                for tab in tabs:
                    pass
                    # print(f"  - Texto: '{tab.text}' | Visible: {tab.is_displayed()} | Enabled: {tab.is_enabled()}", flush=True)
            except Exception as e:
                pass
                # print(f"DEBUG: Error al inspeccionar pestañas: {e}", flush=True)

        # DEBUG: Inspeccionar todas las pestañas con data-toggle="tab" en toda la página
        try:
            all_tabs = driver.find_elements(By.XPATH, "//a[@data-toggle='tab']")
            # print("DEBUG: Pestañas con data-toggle='tab' en toda la página:", flush=True)
            for tab in all_tabs:
                text = tab.text.strip()
                visible = tab.is_displayed()
                enabled = tab.is_enabled()
                data_toggle = tab.get_attribute("data-toggle")
                # print(f"  - Texto: '{text}' | data-toggle: '{data-toggle}' | Visible: {visible} | Enabled: {enabled}", flush=True)
        except Exception as e:
            pass
            # print(f"DEBUG: Error al inspeccionar pestañas data-toggle: {e}", flush=True)

        # Verificar si la pestaña 'Análisis de Liquidación' ya está activa
        tab_active = False
        try:
            # Verificar si hay una pestaña activa con el texto
            active_tab = driver.find_element(By.XPATH, "//a[contains(@class, 'nav-link active') and contains(text(), 'Analisis de Liquidación')]")
            # print(f"DEBUG: Pestaña activa encontrada: texto='{active_tab.text}', visible={active_tab.is_displayed()}, enabled={active_tab.is_enabled()}", flush=True)
            tab_active = True
            # print("DEBUG: Pestaña 'Análisis de Liquidación' ya está activa.", flush=True)
        except NoSuchElementException:
            # print("DEBUG: Pestaña 'Análisis de Liquidación' no está activa.", flush=True)
            # Verificar si existe la pestaña (no necesariamente activa)
            try:
                analisis_tab = driver.find_element(By.XPATH, "//a[@data-toggle='tab' and contains(text(), 'Analisis de Liquidación')]")
                # print(f"DEBUG: Pestaña encontrada (no activa): texto='{analisis_tab.text}', visible={analisis_tab.is_displayed()}, enabled={analisis_tab.is_enabled()}", flush=True)
            except NoSuchElementException:
                pass
                # print("DEBUG: Pestaña 'Análisis de Liquidación' no encontrada.", flush=True)

        # Asumir que ya estamos en "Gestión de siniestros" desde sondear_siniestros_asignados
        # Solo navegar directamente a la pestaña si no está activa
        if not tab_active:
            print("Navegando a la pestaña 'Análisis de Liquidación'", flush=True)
            analisis_click_element = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.XPATH, "//a[@data-toggle='tab' and contains(text(), 'Analisis de Liquidación')]" )))
            print(f"DEBUG: Elemento clickeable encontrado: texto='{analisis_click_element.text}', visible={analisis_click_element.is_displayed()}, enabled={analisis_click_element.is_enabled()}", flush=True)
            analisis_click_element.click()
            print("DEBUG: Clic realizado en 'Análisis de Liquidación'.", flush=True)
            esperar_pagina_cargada(driver)
        else:
            print("Pestaña 'Análisis de Liquidación' ya está activa. Saltando navegación.", flush=True)

        # DEBUG: Inspeccionar todos los botones disponibles en la página
        # print("DEBUG: Inspeccionando todos los botones en la página...", flush=True)
        try:
            all_buttons = driver.find_elements(By.TAG_NAME, "button")
            # print(f"DEBUG: Encontrados {len(all_buttons)} botones en total:", flush=True)
            for i, btn in enumerate(all_buttons):
                text = btn.text.strip()
                visible = btn.is_displayed()
                enabled = btn.is_enabled()
                attributes = {attr: btn.get_attribute(attr) for attr in ['id', 'class', 'type', 'data-toggle', 'aria-label'] if btn.get_attribute(attr)}
                # print(f"  Botón {i+1}: text='{text}', visible={visible}, enabled={enabled}, attributes={attributes}", flush=True)
        except Exception as e:
            pass
            # print(f"DEBUG: Error al inspeccionar botones: {e}", flush=True)

        # DEBUG: Inspeccionar todas las imágenes con src que contengan 'excel' o 'download'
        # print("DEBUG: Inspeccionando imágenes con src relacionado con Excel o descarga...", flush=True)
        try:
            all_images = driver.find_elements(By.TAG_NAME, "img")
            relevant_images = [img for img in all_images if img.get_attribute("src") and ('excel' in img.get_attribute("src").lower() or 'download' in img.get_attribute("src").lower())]
            # print(f"DEBUG: Encontradas {len(relevant_images)} imágenes relevantes:", flush=True)
            for i, img in enumerate(relevant_images):
                src = img.get_attribute("src")
                alt = img.get_attribute("alt") or ""
                # print(f"  Imagen {i+1}: src='{src}', alt='{alt}'", flush=True)
        except Exception as e:
            pass
            # print(f"DEBUG: Error al inspeccionar imágenes: {e}", flush=True)

        # DEBUG: Verificar elementos con data-toggle u otros atributos relacionados con descarga
        # print("DEBUG: Inspeccionando elementos con data-toggle o atributos de descarga...", flush=True)
        try:
            elements_with_data_toggle = driver.find_elements(By.XPATH, "//*[@data-toggle]")
            # print(f"DEBUG: Encontrados {len(elements_with_data_toggle)} elementos con data-toggle:", flush=True)
            for i, elem in enumerate(elements_with_data_toggle):
                tag = elem.tag_name
                data_toggle = elem.get_attribute("data-toggle")
                text = elem.text.strip()
                visible = elem.is_displayed()
                enabled = elem.is_enabled() if tag in ['button', 'input', 'a'] else 'N/A'
                # print(f"  Elemento {i+1}: tag='{tag}', data-toggle='{data_toggle}', text='{text}', visible={visible}, enabled={enabled}", flush=True)

            # Otros atributos relacionados con descarga
            download_related = driver.find_elements(By.XPATH, "//*[@download or @href[contains(., 'excel') or @href[contains(., 'download')]]")
            # print(f"DEBUG: Encontrados {len(download_related)} elementos con atributos de descarga:", flush=True)
            for i, elem in enumerate(download_related):
                tag = elem.tag_name
                href = elem.get_attribute("href") or ""
                download = elem.get_attribute("download") or ""
                text = elem.text.strip()
                # print(f"  Elemento {i+1}: tag='{tag}', href='{href}', download='{download}', text='{text}'", flush=True)
        except Exception as e:
            pass
            # print(f"DEBUG: Error al inspeccionar elementos con data-toggle: {e}", flush=True)

        # Find and click download button
        # DEBUG: Inspect all buttons matching the current selector before WebDriverWait
        # print("DEBUG: Inspeccionando todos los botones que coinciden con el selector actual antes de WebDriverWait...", flush=True)
        try:
            all_matching_buttons = driver.find_elements(By.XPATH, "//button[.//img[contains(@src, 'excel-icon')]]")
            # print(f"DEBUG: Encontrados {len(all_matching_buttons)} botones que coinciden con el selector:", flush=True)
            for i, btn in enumerate(all_matching_buttons):
                try:
                    img_src = btn.find_element(By.XPATH, ".//img").get_attribute("src")
                    # print(f"  Botón {i+1}: src='{img_src}', class='{btn.get_attribute('class')}', text='{btn.text}', visible={btn.is_displayed()}, enabled={btn.is_enabled()}", flush=True)
                except Exception as e:
                    pass
                    # print(f"  Botón {i+1}: Error al obtener atributos - {e}", flush=True)
        except Exception as e:
            pass
            # print(f"DEBUG: Error al inspeccionar botones coincidentes: {e}", flush=True)

        # DEBUG: Inspect buttons with images before attempting to find download button
        # print("DEBUG: Inspeccionando botones con imágenes antes de buscar el botón de descarga...", flush=True)
        try:
            all_buttons_with_img = driver.find_elements(By.XPATH, "//button[.//img]")
            # print(f"DEBUG: Encontrados {len(all_buttons_with_img)} botones con img:", flush=True)
            for i, btn in enumerate(all_buttons_with_img):
                try:
                    img_src = btn.find_element(By.XPATH, ".//img").get_attribute("src")
                    # print(f"  Botón {i+1}: src='{img_src}', text='{btn.text}', visible={btn.is_displayed()}, enabled={btn.is_enabled()}", flush=True)
                except Exception as e:
                    pass
                    # print(f"  Botón {i+1}: Error al obtener atributos - {e}", flush=True)
        except Exception as e:
            pass
            # print(f"DEBUG: Error al inspeccionar botones con img: {e}", flush=True)

        # DEBUG: Inspect all buttons containing text related to download
        try:
            all_download_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Descargar') or contains(., 'Exportar') or contains(., 'Excel')]")
            # print(f"DEBUG: Encontrados {len(all_download_buttons)} botones con texto de descarga:", flush=True)
            for i, btn in enumerate(all_download_buttons):
                pass
                # print(f"  Botón {i+1}: text='{btn.text}', visible={btn.is_displayed()}, enabled={btn.is_enabled()}", flush=True)
        except Exception as e:
            pass
            # print(f"DEBUG: Error al inspeccionar botones de descarga por texto: {e}", flush=True)

        print("DEBUG: Intentando encontrar el botón de descarga con el selector actualizado...", flush=True)
        try:
            download_button = driver.find_element(By.XPATH, "//button[contains(@class, 'floating-icon')]")
            print("DEBUG: Intentando clic JS en botón de descarga...")
            driver.execute_script("arguments[0].click();", download_button)
            print("DEBUG: Clic JS ejecutado exitosamente")
        except Exception as e:
            print(f"Error al hacer clic en el botón de descarga: {e}")
        
        # Wait for download
        download_dir = "/tmp/downloads"
        timeout = 60
        start_time = time.time()
        file_path = None
        while time.time() - start_time < timeout:
            files = os.listdir(download_dir)
            for file in files:
                if file.endswith('.xlsx') or file.endswith('.xls'):
                    file_path = os.path.join(download_dir, file)
                    break
            if file_path:
                break
            time.sleep(1)
        
        if not file_path:
            print("No se pudo descargar el archivo Excel.")
            return
        
        # Process Excel
        df = pd.read_excel(file_path)
        print("DEBUG: Columnas del Excel:", df.columns.tolist())
        print("DEBUG: Primeras filas del Excel:", df.head())
        df = df[df['N° SINIESTRO'].notna() & (df['N° SINIESTRO'].astype(str).str.strip() != '')]

        # Map columns to consistent structure
        column_mapping = {
            'FechaAsignacion': 'FechaAsignacion',
            'NumeroSiniestro': 'N° SINIESTRO',
            'EstadoContacto': 'EstadoContacto',
            'Patente': 'Patente',
            'NombreAsegurado': 'NombreAsegurado',
            'RutAsegurado': 'RUT ASEGURADO',
            'CorreoAsegurado': 'CorreoAsegurado',
            'TelefonoAsegurado': 'TelefonoAsegurado',
            'Marca': 'MARCA',
            'Modelo': 'MODELO',
            'TipoDanio': 'TIPO DAÑO',
            'FechaEstimadaIngreso': 'FECHA INGRESO'
        }
        
        for index, row in df.iterrows():
            row_data = {'Compania': compania}
            for key, col in column_mapping.items():
                row_data[key] = row.get(col, '')
            yield row_data
        
        # Clean up
        os.remove(file_path)
        
    except Exception as e:
        print(f"Error en sondear_siniestros_liquidacion: {e}")
        traceback.print_exc()
        take_screenshot(driver, "error_liquidacion.png")
    
    print(f"\n--- Proceso de sondeo de liquidación completado. ---", flush=True)
    print(f"\n--- Proceso de sondeo completado. ---", flush=True)

def scrape_full_data(driver):
    """
    Orquesta el proceso completo de scraping para todas las compañías definidas.
    """
    print("--- Iniciando proceso de scraping completo ---", flush=True)
    
    companias = ["BCI", "ZENIT"]

    for compania in companias:
        print(f"\n--- Procesando compañía: {compania.upper()} ---", flush=True)
        if asegurar_contexto(driver, compania):
            yield from sondear_siniestros_asignados(driver, compania)
            yield from sondear_siniestros_liquidacion(driver, compania)
        else:
            print(f"ADVERTENCIA: No se pudo asegurar el contexto para {compania.upper()}. Saltando esta compañía.", flush=True)
            take_screenshot(driver, f"error_contexto_{compania.lower()}.png")
