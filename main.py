from flask import Flask, render_template, request
from flask_dependencies import *

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

    #browser = webdriver.Chrome(options=chrome_options)
    browser = webdriver.Remote(
        command_executor="http://162.19.67.246:4444/wd/hub",
        options=chrome_options
    )

    browser2 = webdriver.Remote(
        command_executor="http://162.19.67.246:4444/wd/hub",
        options=chrome_options
    )

    results = []
    result_item2_list = []

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

            max_results = 3
            results_count = 0

            for i in range(min(max_results, len(elements))): 
                try:
                    scroll_origin = ScrollOrigin.from_element(elements[i])
                    action.scroll_from_origin(scroll_origin, 0, 10).perform()
                    action.move_to_element(elements[i]).perform()
                    WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "hfpxzc")))
                    browser.execute_script("arguments[0].click();", elements[i])
                    time.sleep(5)
                    print(f"Successfully clicked on {i}")

                    h1_element = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "DUwDvf")))
                    restaurant_name = h1_element.text

                    address_element = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.Io6YTe.fontBodyMedium.kR99db")))
                    address = address_element.text

                    phone_button_selector = "button.CsEnBe[aria-label*='téléphone']"
                    phone_element = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, phone_button_selector)))
                    aria_label = phone_element.get_attribute("aria-label")
                    phone_number = aria_label.split(":")[1].strip()

                    address = address.replace("Pl.", "Place")
                    address = address.replace("Av.", "Avenue")
                    address = address.replace("Bd", "Boulevard")
                    address = address.replace("Ter", "T")
                    address = address.replace("Rte", "Route")
                    address = address.replace("Bis", "B")

                    result_item = {
                        "Nom": restaurant_name,
                        "Adresse": address,
                        "Telephone": phone_number,
                    }
                    print(result_item)
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
    final_results = []
    for result in results:

        nom = result["Nom"]
        address = result["Adresse"]
        telephone = result["Telephone"]
        print(f"Searching for {nom} at {address}")
        browser2.get("https://annuaire-entreprises.data.gouv.fr/")
        time.sleep(5)
        search_input = browser2.find_element(By.ID, "search-input-input")
        search_input.clear() 
        search_input.send_keys(address) 
        search_input.send_keys(Keys.RETURN)  

        time.sleep(5)

        address_cleaned = address.replace(",", "")
        result_links = browser2.find_elements(By.CSS_SELECTOR, "a.result-link")
        print(f"Found {len(result_links)} result links")

        for link in result_links:
            link_text = link.text
            link_url = link.get_attribute("href")
            print(f"Checking link: {link_text}")
            link_address = link_text.split("\n")[-1].replace(",", "").lower()
            if ("Hôtels et hébergement similaire" in link_text or "Débits de boissons" in link_text  or "Restauration traditionnelle" in link_text or "Restauration de type rapide" in link_text) and address_cleaned.lower() in link_address:
                dirigeants_element = link.find_element(By.CSS_SELECTOR, "div.styles_icon__Qg4dr")
                dirigeants_text = dirigeants_element.text
                soup = BeautifulSoup(dirigeants_text, "html.parser")
                nom_dirigeant = soup.get_text(strip=True)
                result_item2 = {
                    "Nom": nom,
                    "Adresse": address,
                    "Nom du dirigeant": nom_dirigeant,
                    "Telephone": telephone,
                }

                browser2.execute_script(f"window.open('{link_url}', '_blank');")
                print(f"Successfully opened the link for {nom}")
                window_handles = browser2.window_handles
                browser2.switch_to.window(window_handles[-1])  # Passe à la nouvelle fenêtre/onglet

                # Trouve l'élément h2 spécifique et récupère son texte
                legal_info_elements = browser2.find_elements(By.CSS_SELECTOR, "td.styleSimple_cell__OckvR")
                eighteenth_legal_info_element = legal_info_elements[17]
                eighteenth_legal_info_text = eighteenth_legal_info_element.text
                result_item2 = {
                "Nom": nom,
                "Adresse": address, 
                "Nom du dirigeant": nom_dirigeant,
                "Telephone": telephone,
                "Nombre d employe": eighteenth_legal_info_text # Utiliser la variable modifiée
}
                print(result_item2)
                result_item2_list.append(result_item2)
                print(result_item2)
                # Affiche le texte récupéré
                print(eighteenth_legal_info_text)
                break
        else:
            print("No matching link found")

    browser2.quit()
    return render_template('index.html', results=result_item2_list)

if __name__ == '__main__':
    app.run(debug=True)
