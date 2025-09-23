import os
import json
import traceback
from flask import Flask, Response, stream_with_context
from scraper import (
    setup_driver,
    login_to_bci,
    manejar_popup_bienvenida,
    scrape_full_data
)
from notion_manager import NotionManager
from dotenv import load_dotenv

app = Flask(__name__)

def _run_scraping(driver, stats, siniestros_list):
    """
    Runs the scraping process, yields progress, and populates the siniestros_list.
    """
    try:
        yield "--- Iniciando sondeo de siniestros para todas las compañías...\n".encode('utf-8')
        for siniestro in scrape_full_data(driver):
            try:
                siniestros_list.append(siniestro)
                progress_message = (
                    f"Siniestro encontrado: {siniestro.get('NumeroSiniestro')} "
                    f"({siniestro.get('Compania')})\n"
                )
                yield progress_message.encode('utf-8')
            except GeneratorExit:
                print("Cliente desconectado durante scraping", flush=True)
                break
            except Exception as e:
                print(f"Error procesando siniestro: {e}", flush=True)
                continue
        
        stats["extraidos"] = len(siniestros_list)
        yield f"--- Sondeo finalizado. Se encontraron {stats['extraidos']} siniestros en total.\n".encode('utf-8')
    except GeneratorExit:
        print("Cliente desconectado durante _run_scraping", flush=True)
        stats["extraidos"] = len(siniestros_list)
    except Exception as e:
        print(f"Error en _run_scraping: {e}", flush=True)
        yield f"Error durante scraping: {str(e)}\n".encode('utf-8')

def _run_notion_integration(siniestros_extraidos):
    """
    Runs the Notion integration process and yields progress updates.
    """
    try:
        yield "\n--- Iniciando integración con Notion...\n".encode('utf-8')
        notion_token = os.getenv("NOTION_TOKEN")
        db_ids = {
            "DATABASE_ID_SINIESTROS": os.getenv("DATABASE_ID_SINIESTROS"),
            "DATABASE_ID_PATENTES": os.getenv("DATABASE_ID_PATENTES"),
            "DATABASE_ID_CLIENTES": os.getenv("DATABASE_ID_CLIENTES"),
        }
        notion_manager = NotionManager(notion_token, db_ids)
        notion_manager.process_and_insert_siniestros(siniestros_extraidos)
        yield "--- Integración con Notion finalizada.\n".encode('utf-8')
    except GeneratorExit:
        print("Cliente desconectado durante integración con Notion", flush=True)
    except Exception as e:
        print(f"Error en integración con Notion: {e}", flush=True)
        yield f"Error durante integración con Notion: {str(e)}\n".encode('utf-8')

@app.route('/run', methods=['POST'])
def trigger_run():
    """
    This endpoint triggers the automation and streams the results.
    """
    def generate():
        load_dotenv()
        
        stats = {"extraidos": 0, "error": None}
        driver = None
        siniestros_extraidos = []
        
        try:
            yield "--- Iniciando proceso completo...\n".encode('utf-8')
            driver = setup_driver()
            if not driver:
                raise Exception("Fallo al iniciar el driver.")

            yield "--- Driver inicializado. Realizando login...\n".encode('utf-8')
            api_key_2captcha = os.getenv("API_KEY_2CAPTCHA")
            user = os.getenv("BCI_USER")
            password = os.getenv("BCI_PASS")

            if not login_to_bci(driver, user, password, api_key_2captcha):
                raise Exception("Fallo en el login.")

            yield "--- Login exitoso. Iniciando secuencia de operaciones...\n".encode('utf-8')

            # Run scraping and notion integration, yielding progress from them
            try:
                for progress_update in _run_scraping(driver, stats, siniestros_extraidos):
                    yield progress_update
                
                if siniestros_extraidos:
                    for progress_update in _run_notion_integration(siniestros_extraidos):
                        yield progress_update
                    
                    # Yield the final extracted data for verification
                    yield b"\n--- DATOS EXTRAIDOS (JSON) ---\n"
                    yield (json.dumps(siniestros_extraidos, indent=2, ensure_ascii=False) + "\n").encode('utf-8')
                    yield b"--- FIN DE DATOS EXTRAIDOS ---"
            except GeneratorExit:
                print("Cliente desconectado durante procesamiento principal", flush=True)
                stats["error"] = "Cliente desconectado"

        except GeneratorExit:
            print("Cliente desconectado - cerrando proceso limpiamente", flush=True)
            stats["error"] = "Cliente desconectado"
        except Exception as e:
            error_message = f"--- Error catastrófico: {e}\n{traceback.format_exc()}"
            print(error_message, flush=True)
            try:
                yield error_message.encode('utf-8')
            except (BrokenPipeError, ConnectionResetError):
                print("No se puede enviar mensaje de error - cliente desconectado", flush=True)
            stats["error"] = str(e)
        finally:
            if driver:
                try:
                    yield "--- Cerrando el navegador del scraper...\n".encode('utf-8')
                except (BrokenPipeError, ConnectionResetError, GeneratorExit):
                    print("Cliente desconectado - cerrando driver sin mensaje", flush=True)
                try:
                    driver.quit()
                    print("Driver cerrado correctamente", flush=True)
                except Exception as e:
                    print(f"Error cerrando driver: {e}", flush=True)
            try:
                yield b"\n--- PROCESO FINALIZADO ---\n"
                yield (json.dumps(stats, indent=4, ensure_ascii=False) + "\n").encode('utf-8')
            except (BrokenPipeError, ConnectionResetError, GeneratorExit):
                print("Cliente desconectado - proceso finalizado sin mensaje final", flush=True)
        
    def safe_generate():
        try:
            for chunk in generate():
                yield chunk
        except (BrokenPipeError, ConnectionResetError, GeneratorExit) as e:
            print(f"Cliente desconectado durante streaming: {type(e).__name__}", flush=True)
        except Exception as e:
            print(f"Error durante streaming: {e}", flush=True)
            try:
                yield f"Error durante el proceso: {str(e)}\n".encode('utf-8')
            except:
                pass
    
    return Response(stream_with_context(safe_generate()), mimetype='text/plain')

if __name__ == '__main__':
    print(">>> Iniciando servidor Flask para pruebas locales. Escuchando en http://0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000)
