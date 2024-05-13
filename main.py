from flask import Flask, render_template, request
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium import webdriver
from bs4 import BeautifulSoup
import time
import ssl
import json
import re

app = Flask(__name__)

ssl._create_default_https_context = ssl._create_unverified_context

@app.route('/')
def index():
    return render_template('index.html')
@app.route('/scrape_progressive')
def scrape_progressive():
    search_query = request.args.get('search_query')
    link = f"https://www.google.com/maps/search/{search_query}" 
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")

    browser = webdriver.Chrome(options=chrome_options)

    results = []

    def progressive_extraction():
        nonlocal results
        action = ActionChains(browser)
        prev_len = None  
        same_len_count = 0 
        processed_urls = {}  

        while True:
            elements = browser.find_elements(By.CSS_SELECTOR, "a.hfpxzc")
            if len(elements) == prev_len:
                same_len_count += 1
            else:
                prev_len = len(elements)
                same_len_count = 0
            if same_len_count >= 3:
                break

            var = len(elements)
            scroll_origin = ScrollOrigin.from_element(elements[-1])
            action.scroll_from_origin(scroll_origin, 0, 30).perform()
            time.sleep(2)

        max_results = 10  # Limite de 10 résultats
        results_count = 0

        for i in range(min(10, len(elements))):  # Itérer sur un maximum de 10 éléments
            try:
                scroll_origin = ScrollOrigin.from_element(elements[i])
                action.scroll_from_origin(scroll_origin, 0, 10).perform()
                action.move_to_element(elements[i]).perform()
                WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "hfpxzc")))
                browser.execute_script("arguments[0].click();", elements[i])
                time.sleep(5)
                print(f"Successfully clicked on {i}")

                # Récupérer le texte de l'élément h1
                h1_element = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "DUwDvf")))
                restaurant_name = h1_element.text

                # Récupérer l'adresse
                address_element = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.Io6YTe.fontBodyMedium.kR99db")))
                address = address_element.text

                # Remplacer les abréviations dans l'adresse
                address = address.replace("Pl.", "Place")
                address = address.replace("Av.", "Avenue")
                address = address.replace("Bd", "Boulevard")
                address = address.replace("Ter", "T")
                address = address.replace("Rte", "Route")
                address = address.replace("Bis", "B")

                # Récupérer le contenu de la page
                page_source = browser.page_source

                # Utiliser une expression régulière pour trouver le numéro de téléphone au format spécifique
                phone_pattern = re.compile(r'(\d{2} \d{2} \d{2} \d{2} \d{2})')
                matches = phone_pattern.findall(page_source)

                if matches:
                    phone_number = matches[0]  # Prendre le premier match trouvé
                else:
                    phone_number = None  # Aucun numéro de téléphone trouvé dans le format spécifié

                # Créer un dictionnaire avec les données récupérées
                result_item = {
                    "Nom de l'établissement": restaurant_name,
                    "Addresse": address,
                    "Téléphone": phone_number
                }
                results.append(result_item)

            except Exception as e:
                print(f"Error occurred while clicking element {i}: {e}")

            results_count += 1
            if results_count >= max_results:
                break

    browser.get(link)
    time.sleep(10)
    try:
        accept_button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.VfPpkd-LgbsSe")))
        accept_button.click()
    except Exception as e:
        print("Error occurred while clicking 'Accept All':", e)

    progressive_extraction()

    # Une fois le scraping de Google Maps terminé, effectuez la recherche sur le site annuaire-entreprises.data.gouv.fr
    for result in results:
        address = result["Addresse"]

        # Aller sur le site annuaire-entreprises.data.gouv.fr
        browser.get("https://annuaire-entreprises.data.gouv.fr/")

        # Attendre que la page se charge
        time.sleep(5)

        # Trouver l'élément de recherche
        search_input = browser.find_element(By.ID, "search-input-input")

        # Insérer l'adresse récupérée dans le champ de recherche
        search_input.clear()  # Assurez-vous que le champ est vide
        search_input.send_keys(address)  # Insérer l'adresse récupérée
        search_input.send_keys(Keys.RETURN)  # Appuyer sur la touche Entrée pour lancer la recherche

        # Attendre que la page se charge après la recherche
        try:
            # Attendre que la page se charge après la recherche
            wait = WebDriverWait(browser, 10)  # Attendre jusqu'à 10 secondes maximum
            wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "style_result-item__fKcQt")))
        except TimeoutException:
            print("La recherche n'a pas abouti. Passer à la prochaine recherche.")
            continue  # Passer à la prochaine itération de la boucle


        # Maintenant, faire défiler la page vers le bas pour charger davantage de contenu
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # Attendre un court instant pour que le contenu supplémentaire se charge
        time.sleep(3)  # Vous pouvez ajuster ce délai en fonction de la vitesse de chargement de la page

        # Extraire les données de la page
        page_source = browser.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        results_divs = soup.find_all("div", class_="style_result-item__fKcQt")
        for div in results_divs:
            badge = div.find("span", class_="styles_frBadge__s26DO")
            if badge and "cessée" not in badge.text:
                name_element = div.find("div", class_="style_dirigeants-or-elus__Qzy9P").find("span")
                if name_element:
                    name_parts = name_element.text.split("(")
                    if len(name_parts) >= 2:
                        nom = name_parts[0].strip()
                        prenom = name_parts[1].replace(")", "").strip()
                        print("Nom:", nom)
                        print("Prénom:", prenom)

        # Afficher un message dans la console pour indiquer que la recherche est terminée
        print("Recherche papier réussie")

    browser.quit()

    return json.dumps(results)  # retourner les résultats en tant que JSON

if __name__ == '__main__':
    app.run(debug=True)
