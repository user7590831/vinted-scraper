import requests
import os
import sqlite3
import argparse
import time
import cloudscraper
import re
import logging

# ArgParse
parser = argparse.ArgumentParser(description='Vinted & Depop Scraper/Downloader. Default downloads Vinted')

# Define command line arguments
parser.add_argument('--depop','-d',dest='Depop', action='store_true', help='Download Depop data.')
parser.add_argument('--private_msg','-p',dest='priv_msg', action='store_true', help='Download images from private messages from Vinted')
parser.add_argument('--user_id','-u',dest='user_id', action='store', help='Your own userid', required=False)
parser.add_argument('--session_id','-s',dest='session_id', action='store', help='Session id cookie for Vinted', required=False)
parser.add_argument('--disable-file-download','-n',dest='disable_file_download', action='store_true', help='Disable file download (Currently only working for depop)', required=False)
parser.add_argument('--sold_items','-g',dest='sold_items', action='store_true', help='Also download sold items (depop)', required=False)
parser.add_argument('--start_from','-b',dest='start_from', action='store', help='Begin from a specific item (depop)', required=False)
parser.add_argument('--maximum_images','-i',dest='maximum_images', action='store', help='Set a maximum amount of image to download. 1 image by default (vinted)', required=False)
parser.add_argument('--debug','-v',dest='debug', action='store_true', help='Enable debug logging', required=False)

args = parser.parse_args()

# Configure logging and validate arguments
if args.debug:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
if args.disable_file_download and not args.Depop:
    logging.error("-n only works with Depop. Use -n -d to disable filedownloads from Depop")
    exit(1)

# Create downloads folders if they do not exist
if not os.path.exists('downloads'):
    os.makedirs('downloads')

directory_path = "downloads/Avatars/"
try:
    os.mkdir(directory_path)
    logging.info(f"Directory created at {directory_path}")
except OSError as e:
    if os.path.exists(directory_path):
        logging.warning(f"Folder already exists at {directory_path}")
    else:
        logging.error(f"Creation of the directory failed at {directory_path}")
        logging.debug(f"Error: {e}")

# Connect to SQLite database
sqlite_file = 'data.sqlite'
conn = sqlite3.connect(sqlite_file)
c = conn.cursor()

# Create tables if they do not exist
c.execute('''CREATE TABLE IF NOT EXISTS Data
             (ID, User_id, Sold, Url, Favourite, Gender, Category, subcategory, size, State, Brand, Colors, Price, Image, Images, Description, Title, Platform)''')

c.execute('''CREATE TABLE IF NOT EXISTS Depop_Data
             (ID, User_id, Url, Sold, Gender, Category, subcategory, size, State, Brand, Colors, Price, Image, Description, Title, Platform, Address, discountedPriceAmount, dateUpdated)''')

c.execute('''CREATE TABLE IF NOT EXISTS Users
             (Username, User_id, Gender, Given_item_count, Taken_item_count, Followers_count, Following_count, Positive_feedback_count, Negative_feedback_count, Feedback_reputation, Avatar, Created_at, Last_loged_on_ts, City_id, City, Country_title, Verification_email, Verification_facebook, Verification_google, Verification_phone, Platform)''')

c.execute('''CREATE TABLE IF NOT EXISTS Depop_Users
             (Username, User_id UNIQUE, bio, first_name, followers, following, initials, items_sold, last_name, last_seen, Avatar, reviews_rating, reviews_total, verified, website)''')

c.execute('''CREATE TABLE IF NOT EXISTS Vinted_Messages
             (thread_id, from_user_id, to_user_id, msg_id, body, photos)''')

conn.commit()

# Function to update columns of Data with new version of the script
def update_col():
    logging.info("Updating columns of Data Table with new version of the script: add Url and Favourite field")
    for column in ['Url', 'Favourite']:
        try:
            c.execute(f'ALTER TABLE Data ADD {column};')
            conn.commit()
            logging.info(f"Column {column} added")
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                logging.debug(f"Column {column} already exists")
            else:
                logging.error(f"Can't add column {column}: {e}")


def ensure_directory(path):
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            logging.info(f"Directory created: {path}")
        except OSError as e:
            logging.error(f"Creation of directory {path} failed: {e}")
    else:
        logging.debug(f"Directory already exists: {path}")

# Function to extract CSRF token from HTML
def extract_csrf_token(text):
    match = re.search(r'"CSRF_TOKEN":"([^"]+)"', text)
    if match:
        return match.group(1)
    else:
        return None

# Function to create a Vinted session
def vinted_session():
    s = cloudscraper.create_scraper()
    s.headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en',
        'DNT': '1',
        'Connection': 'keep-alive',
        'TE': 'Trailers',
    }
    req = s.get("https://www.vinted.nl/")
    csrfToken = extract_csrf_token(req.text)
    if csrfToken:
        s.headers['X-CSRF-Token'] = csrfToken
    return s

# Function to download private messages from Vinted
def download_priv_msg(session_id, user_id):
    s = cloudscraper.create_scraper()
    s.headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en',
        'DNT': '1',
        'Connection': 'keep-alive',
        'TE': 'Trailers',
        'Cookie': f"_vinted_fr_session={session_id};"
    }
    logging.info(f"Session ID: {session_id}")
    data = s.get(f"https://www.vinted.nl/api/v2/users/{user_id}/msg_threads")
    if data.status_code == 403:
        # Access denied
        logging.error(f"Error: Access Denied\nCan't get content from 'https://www.vinted.nl/api/v2/users/{user_id}/msg_threads'")
        exit(1)
    data = data.json()
    try:
        os.mkdir(f"downloads/Messages/")
    except OSError:
        if os.path.isdir(f"downloads/Messages/"):
            logging.warning("Directory already exists")
        else:
            logging.error("Creation of the directory failed")
    if not "msg_threads" in data:
        logging.error("Error: Can't find any messages.\nPlease make sure you entered the sessionid correctly")
        exit(1)
    for msg_threads in data['msg_threads']:
        id = msg_threads['id']
        msg_data = s.get(f"https://www.vinted.nl/api/v2/users/{user_id}/msg_threads/{id}").json()

        thread_id = msg_data['msg_thread']['id']
        for message in msg_data['msg_thread']['messages']:
            try:
                photo_data = message['entity']['photos']
            except:
                continue
            if len(photo_data) > 0:
                try:
                    os.mkdir(f"downloads/Messages/{message['entity']['user_id']}")
                except OSError as e:
                    if os.path.isdir(f"downloads/Messages/{message['entity']['user_id']}"):
                        logging.warning(f"Directory already exists: downloads/Messages/{message['entity']['user_id']}")
                    else:
                        logging.error(f"Creation of the directory failed: {e}")

                from_user_id = message['entity']['user_id']
                msg_id = message['entity']['id']
                body = message['entity'].get('body', '')
                photo_list = []
                for photo in message['entity']['photos']:
                    req = requests.get(photo['full_size_url'])

                    filepath = f"downloads/Messages/{from_user_id}/{photo['id']}.jpeg"
                    photo_list.append(filepath)
                    if not os.path.isfile(filepath):
                        logging.info(f"Downloading photo ID: {photo['id']}")
                        with open(filepath, 'wb') as f:
                            f.write(req.content)
                        logging.info(f"Image saved to {filepath}")
                    else:
                        logging.info('File already exists, skipped.')
                if int(from_user_id) == int(user_id):
                    to_user_id = msg_data['msg_thread']['opposite_user']['id']
                else:
                    to_user_id = user_id
                # Save to DB

                params = (thread_id, from_user_id, to_user_id, msg_id, body, str(photo_list))
                c.execute(
                    "INSERT INTO Vinted_Messages(thread_id, from_user_id, to_user_id, msg_id, body, photos)VALUES (?,?,?,?,?,?)",
                    params)
                conn.commit()

# Function to get all items from a user on Vinted
def get_all_items(s, USER_ID, total_pages, items):
    for page in range(int(total_pages)):
        page += 1
        url = f'https://www.vinted.nl/api/v2/wardrobe/{USER_ID}/items?page={page}&per_page=200000'
        r = s.get(url).json()
        if 'pagination' not in r:
            logging.warning(f"No pagination found on page {page}, skipping")
            continue
        logging.info(f"Fetching page {page + 1}/{r['pagination']['total_pages']}")
        if 'items' in r:
            items.extend(r['items'])

# Function to download data from Vinted for a list of user IDs
def download_vinted_data(userids, s):
    """
    Download data from Vinted for a list of user IDs.

    Args:
        userids (list): List of user IDs to download data for.
        s (requests.Session): Session object to make requests.

    Returns:
        None
    """
    Platform = "Vinted"
    for USER_ID in userids:
        USER_ID = USER_ID.strip()
        
        # Get user profile data
        url = f"https://www.vinted.nl/api/v2/users/{USER_ID}"
        r = s.get(url)
        
        if r.status_code == 200:
            jsonresponse = r.json()
            data = jsonresponse['user']
            #get data
            username = data['login']
            try:
                gender = data['gender']
            except:
                gender = None
            given_item_count = data['given_item_count']
            taken_item_count = data['taken_item_count']
            followers_count = data['followers_count']
            following_count = data['following_count']
            positive_feedback_count = data['positive_feedback_count']
            negative_feedback_count = data['negative_feedback_count']
            feedback_reputation = data['feedback_reputation']
            try:
                created_at = data['created_at']
            except KeyError:
                created_at = ""
            last_loged_on_ts = data['last_loged_on_ts']
            city_id = data['city_id']
            city = data['city']
            country_title = data['country_title']
            verification_email = data.get('verification', {}).get('email', {}).get('valid', None)
            verification_facebook = data.get('verification', {}).get('facebook', {}).get('valid', None)
            verification_google = data.get('verification', {}).get('google', {}).get('valid', None)
            verification_phone = data.get('verification', {}).get('phone', {}).get('valid', None)

            # Handle user avatar
            if data['photo']:
                photo = data['photo']['full_size_url']
                photo_id = data['photo']['id']
                
                try:
                    os.mkdir("downloads/Avatars/")
                    logging.info("Directory created at downloads/Avatars/")
                except OSError as e:
                    if os.path.exists("downloads/Avatars/"):
                        logging.warning("Folder already exists at downloads/Avatars/")
                    else:
                        logging.error("Creation of the directory failed")
                        logging.debug(f"Error: {e}")
                
                req = requests.get(photo)
                filepath = f'downloads/Avatars/{photo_id}.jpeg'
                
                if not os.path.isfile(filepath):
                    with open(filepath, 'wb') as f:
                        f.write(req.content)
                    logging.info(f"Avatar saved to {filepath}")
                else:
                    logging.info('File already exists, skipped.')
                
                avatar_path = filepath
            else:
                avatar_path = ""

            # Save user data to database
            params = (
                username, USER_ID, gender, given_item_count, taken_item_count, followers_count, following_count,
                positive_feedback_count, negative_feedback_count, feedback_reputation, avatar_path, created_at,
                last_loged_on_ts, city_id, city, country_title, verification_email, verification_google,
                verification_facebook, verification_phone
            )
            
            c.execute(
                "INSERT INTO Users(Username, User_id, Gender, Given_item_count, Taken_item_count, Followers_count, "
                "Following_count, Positive_feedback_count, Negative_feedback_count, Feedback_reputation, Avatar, "
                "Created_at, Last_loged_on_ts, City_id, City, Country_title, Verification_email, Verification_facebook, "
                "Verification_google, Verification_phone) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                params
            )
            conn.commit()

            # Fetch user items
            USER_ID = USER_ID.strip('\n')
            url = f'https://www.vinted.nl/api/v2/wardrobe/{USER_ID}/items?page=1&per_page=200000'
            logging.info('ID=' + str(USER_ID))

            r = s.get(url)
            items = []
            response_json = r.json()
            logging.debug(f"API Response keys: {response_json.keys()}")

            if 'pagination' not in response_json:
                if response_json.get('code') == 104:
                    logging.info(f"User {USER_ID} not found on Vinted (content deleted or does not exist)")
                else:
                    logging.warning(f"No pagination found for user {USER_ID}, response may be empty or in error format")
                    logging.debug(f"Full response: {response_json}")
                continue
                
            logging.info(f"Fetching page 1/{response_json['pagination']['total_pages']}")
            if r.status_code == 404:
                logging.warning(f"User '{USER_ID}' not found")
                continue
            items.extend(response_json['items'])
            
            if response_json['pagination']['total_pages'] > 1:
                logging.info(f"User has more than {len(items)} items. fetching next page....")
                get_all_items(s, USER_ID, response_json['pagination']['total_pages'], items)
            
            products = items
            logging.info(f"Total items: {len(products)}")

            if r.status_code == 200:
                if products:
                    # Download all products
                    path = f"downloads/{USER_ID}/"
                    
                    try:
                        os.mkdir(path)
                    except OSError as e:
                        if os.path.exists(path):
                            logging.warning(f"Folder already exists at {path}")
                        else:
                            logging.error(f"Creation of the directory {path} failed: {e}")
                    else:
                        logging.info(f"Successfully created the directory {path}")

                    for product in products:
                        if args.debug and product == products[0]:
                            logging.debug(f"Product keys: {product.keys()}")
                        
                        img = product['photos']
                        ID = product['id']
                        User_id = product['user_id']
                        Url = product.get('url', '')
                        Favourite = product.get('favourite_count', 0)
                        description = product.get('description', '')
                        Gender = product['user'].get('gender', None)
                        Category = product.get('catalog_id', '')
                        size = product.get('size', '')
                        State = product.get('status', '')
                        Brand = product.get('brand', '')
                        Colors = product.get('color1', '')
                        price_data = product.get('price', {})
                        Price = f"{price_data.get('amount', 0)} {price_data.get('currency_code', '')}" if price_data else ''
                        Images = product['photos']
                        title = product.get('title', '')
                        path = f"downloads/{User_id}/"

                        if Images:
                            # If parameter -i download a maximum of n images
                            if args.maximum_images:
                                try:
                                    count_img = int(args.maximum_images)
                                except ValueError:
                                    logging.error("Invalid value for maximum_images: This argument needs to be a number")
                                    continue
                                if count_img <= 0:
                                    logging.error("Maximum images must be greater than 0")
                                    continue
                                if count_img > len(img):
                                    count_img = len(img)
                            else:
                                count_img = len(img)

                            for image in Images[:count_img]:
                                full_size_url = image['full_size_url']
                                img_name = image['high_resolution']['id']
                                filepath = f'downloads/{USER_ID}/{img_name}.jpeg'
                                
                                if not os.path.isfile(filepath):
                                    req = requests.get(full_size_url)
                                    params = (
                                        ID, User_id, Url, Favourite, Gender, Category, size, State, Brand, Colors, Price,
                                        filepath, description, title, Platform
                                    )
                                    
                                    try:
                                        c.execute(
                                            "INSERT INTO Data(ID, User_id, Url, Favourite, Gender, Category, size, State, "
                                            "Brand, Colors, Price, Images, description, title, Platform) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                            params
                                        )
                                    except Exception as e:
                                        logging.error(f"Can't execute query: {e}")
                                        update_col()
                                        c.execute(
                                            "INSERT INTO Data(ID, User_id, Url, Favourite, Gender, Category, size, State, "
                                            "Brand, Colors, Price, Images, description, title, Platform) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                            params
                                        )
                                    conn.commit()
                                    
                                    with open(filepath, 'wb') as f:
                                        f.write(req.content)
                                    logging.info(f"Image saved to {filepath}")
                                else:
                                    logging.info('File already exists, skipped.')
                else:
                    logging.info('User has no products')
            elif r.status_code == 429:
                logging.info(f"Ratelimit waiting {r.headers['Retry-After']} seconds...")
                limit = round(int(r.headers['Retry-After']) / 2)
                
                for i in range(limit, 0, -1):
                    print(f"{i}", end="\r", flush=True)
                    time.sleep(1)
                continue
        else:
            logging.info(f"User {USER_ID} does not exist")
    
    conn.close()

def get_all_depop_items(data, baseurl, ids_list, args, begin, s, data_key='objects', id_key='id'):
    if args.start_from:
        for item in data[data_key]:
            item_id = item.get(id_key) or item.get('slug')
            if item_id and item_id not in ids_list:
                if args.start_from == item_id or begin:
                    begin = True
                    ids_list.append(item_id)
    else:
        for item in data[data_key]:
            item_id = item.get(id_key) or item.get('slug')
            if item_id and item_id not in ids_list:
                ids_list.append(item_id)

    while True:
        if data['meta'].get('end'):
            return ids_list

        url = baseurl + f"&offset_id={data['meta']['last_offset_id']}"
        logging.info(url)
        try:
            data = s.get(url).json()
        except:
            logging.error(s.get(url).text)
            exit()

        if args.start_from:
            for item in data[data_key]:
                item_id = item.get(id_key) or item.get('slug')
                if item_id and item_id not in ids_list:
                    if args.start_from == item_id or begin:
                        begin = True
                        ids_list.append(item_id)
            if data['meta'].get('end'):
                break
        else:
            for item in data[data_key]:
                item_id = item.get(id_key) or item.get('slug')
                if item_id and item_id not in ids_list:
                    ids_list.append(item_id)
            if data['meta'].get('end'):
                break

    return ids_list

def download_depop_data(userids):
    Platform = "Depop"
    headers = {"referer":"https://www.depop.com/"}
    s = cloudscraper.create_scraper(browser={
        'browser': 'firefox',
        'platform': 'windows',
        'desktop': True
    })
    s.headers.update(headers)
    s.get("https://depop.com")
    for userid in userids:
        userid = userid.strip()
        search_data = s.get(f"https://api.depop.com/api/v1/search/users/top/?q={userid}").json()
        item = None
        for item in search_data['objects']:
            if item['username'] == userid:
                logging.info(f"User {userid} has userID {item['id']}")
                break
        if item is None:
            logging.warning(f"User {userid} not found")
            continue
        real_userid = item['id']
        slugs = []
        url = f"https://api.depop.com/api/v1/users/{real_userid}/"
        logging.debug(url)
        data = s.get(url).json()

        id = str(data['id'])

        last_seen = data.get('last_seen')
        bio = data.get('bio')
        followers = data.get('followers')
        following = data.get('following')
        initials = data.get('initials')
        items_sold = data.get('items_sold')
        last_name = data.get('last_name', '')
        first_name = data.get('first_name', '')
        reviews_rating = data.get('reviews_rating')
        reviews_total = data.get('reviews_total')
        username = data.get('username', '')
        verified = data.get('verified')
        website = data.get('website')
        filepath = None

        if data.get('picture_data'):
            photo = data['picture_data']['formats']['U0']['url']
            logging.debug(photo)
            ensure_directory("downloads/Avatars/")
            req = s.get(photo)
            filepath = f'downloads/Avatars/{id}.jpeg'
            if not os.path.isfile(filepath):
                with open(filepath, 'wb') as f:
                    f.write(req.content)
                logging.info(f"Avatar saved to {filepath}")
            else:
                logging.debug('Avatar file already exists, skipped.')
        else:
            logging.debug("No avatar found")


        params = (username, id, bio, first_name, followers, following, initials, items_sold, last_name, last_seen, filepath, reviews_rating, reviews_total, verified, website)
        c.execute(
            "INSERT OR IGNORE INTO Depop_Users(Username, User_id, bio, first_name, followers, following, initials, items_sold, last_name, last_seen, Avatar, reviews_rating, reviews_total, verified, website) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            params)
        conn.commit()


        baseurl = f"https://api.depop.com/api/v1/users/{real_userid}/products/?limit=200"
        data = s.get(baseurl).json()

        logging.info("Fetching all products...")
        begin = False
        product_ids = []
        product_ids = get_all_depop_items(data, baseurl, product_ids, args, begin, s, data_key='objects', id_key='id')

        if args.sold_items:
            baseurl = f"https://api.depop.com/api/v1/users/{real_userid}/filteredProducts/sold?limit=200"
            data = s.get(baseurl).json()
            product_ids = get_all_depop_items(data, baseurl, product_ids, args, begin, s, data_key='products', id_key='slug')
            product_ids = get_all_depop_items(data, baseurl, product_ids, args, begin, s, data_key='objects', id_key='id')

        logging.info("Got all products. Starting download...")
        logging.info(f"Total products: {len(product_ids)}")
        path = "downloads/" + str(userid) + '/'
        ensure_directory(path)

        for product_id_ in product_ids:
            logging.debug(f"Processing item: {product_id_}")
            url = f"https://api.depop.com/api/v1/products/{product_id_}/"
            try:
                product_data = s.get(url)
                if product_data.status_code == 200:
                    product_data = product_data.json()
                elif product_data.status_code == 429:
                    logging.warning("Rate limit hit, waiting 60 seconds...")
                    limit = 60
                    for i in range(limit, 0, -1):
                        print(f"{i}", end="\r", flush=True)
                        time.sleep(1)
                    continue
                elif product_data.status_code == 404:
                    logging.warning("Product not found")
                    continue
                else:
                    logging.warning(f"Unexpected status code: {product_data.status_code}")
                    continue
            except ValueError:
                logging.error("Error decoding JSON data. Skipping...")
                continue
            #print(json.dumps(product_data, indent=4))
            product_id = product_data['id']
            Gender = product_data.get('gender')
            try:
                Category = product_data['group']
            except KeyError:
                Category = product_data.get('categoryId')
            subcategory = product_data.get('productType')
            address = product_data.get('address')
            dateUpdated = product_data.get('pub_date')
            State = product_data.get('condition')

            Price = f"{product_data['price_amount']} {product_data['price_currency']}"
            description = product_data['description']
            Sold = product_data['status']
            slug = product_data['slug']
            title = slug.replace("-", " ")

            Colors = product_data.get('colour', [])
            discountedPriceAmount = product_data.get('price', {}).get('discountedPriceAmount')
            Brand = product_data.get('brand')
            sizes = [size['name'] for size in product_data.get('sizes', [])]


            for images in product_data['pictures_data']:
                full_size_url = images['formats']['P0']['url']
                img_name = images['id']

                filepath = 'downloads/' + str(userid) + '/' + str(img_name) + '.jpg'
                if not args.disable_file_download:
                    if not os.path.isfile(filepath):
                        c.execute(f"SELECT ID FROM Depop_Data WHERE ID = {product_id}")
                        result = c.fetchone()
                        if result:
                            c.execute('''UPDATE Depop_Data SET Image = ? WHERE ID = ?''', (filepath, product_id))
                            conn.commit()
                            req = requests.get(full_size_url)
                            with open(filepath, 'wb') as f:
                                f.write(req.content)
                            logging.info(f"Image saved to {filepath}")
                        else:
                            logging.debug(f"Image: {img_name}, URL: {full_size_url}")
                            req = requests.get(full_size_url)
                            params = (
                            product_id, id, Sold, Gender, Category, subcategory, ','.join(sizes), State, Brand, ','.join(Colors), Price, filepath, description, title, Platform, address, discountedPriceAmount, dateUpdated)
                            c.execute(
                                "INSERT OR IGNORE INTO Depop_Data(ID, User_id, Sold, Gender, Category, subcategory, size, State, Brand, Colors, Price, Image, Description, Title, Platform, Address, discountedPriceAmount, dateUpdated)VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                params)
                            conn.commit()
                            with open(filepath, 'wb') as f:
                                f.write(req.content)
                            logging.info(f"Image saved to {filepath}")
                    else:
                        logging.debug('File already exists, skipped.')
                elif args.disable_file_download:
                    c.execute(
                        f"SELECT ID FROM Depop_Data WHERE ID = {product_id}")
                    result = c.fetchone()
                    if result:
                        #Already exists
                        continue
                    else:
                        params = (
                            product_id, Sold, id, Gender, Category, subcategory, ','.join(sizes), State, Brand, ','.join(Colors),
                            Price, description, title, Platform, address, discountedPriceAmount, dateUpdated)
                        c.execute(
                            "INSERT OR IGNORE INTO Depop_Data(ID, Sold, User_id, Gender, Category, subcategory, size, State, Brand, Colors, Price, description, title, Platform, Address, discountedPriceAmount, dateUpdated)VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            params)
                        conn.commit()

            if product_data.get('videos'):
                for x in product_data['videos']:
                    for source in x['outputs']:
                        if source['format'] == 'MP4':
                            video_url = source['url']
                            file_name = video_url.split('/')[5]
                            filepath = 'downloads/' + str(userid) + '/' + str(file_name)
                            if not args.disable_file_download:
                                if not os.path.isfile(filepath):
                                    req = requests.get(video_url)
                                    params = (
                                        product_id, Sold, id, Gender, Category, subcategory, ','.join(sizes), State, Brand,
                                        ','.join(Colors), Price, filepath, Platform, address, discountedPriceAmount, description, title, dateUpdated)
                                    c.execute(
                                        "INSERT OR IGNORE INTO Depop_Data(ID, Sold, User_id, Gender, Category, subcategory, size, State, Brand, Colors, Price, Image, description, title, Platform, Address, discountedPriceAmount, dateUpdated)VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                        params)
                                    conn.commit()
                                    with open(filepath, 'wb') as f:
                                        f.write(req.content)
                                    logging.info(f"Video saved to {filepath}")
                                else:
                                    logging.debug('File already exists, skipped.')
                            elif args.disable_file_download:
                                c.execute(f"SELECT ID FROM Depop_Data WHERE ID = {product_id}")
                                result = c.fetchone()
                                if not result:
                                    params = (
                                        product_id, Sold, id, Gender, Category, subcategory, ','.join(sizes), State,
                                        Brand, ','.join(Colors),
                                        Price, description, title, Platform, address, discountedPriceAmount, dateUpdated)
                                    c.execute(
                                        "INSERT OR IGNORE INTO Depop_Data(ID, Sold, User_id, Gender, Category, subcategory, size, State, Brand, Colors, Price, description, title, Platform, Address, discountedPriceAmount, dateUpdated)VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                        params)
                                    conn.commit()



#Import users from txt file
with open('users.txt', 'r', encoding='utf-8') as list_of_users:
            userids = list_of_users.readlines()

if args.Depop:
    download_depop_data(userids)
elif args.priv_msg:
    if args.user_id and args.session_id:
        user_id = args.user_id
        session_id = args.session_id
        download_priv_msg(session_id, user_id)
    else:
        logging.error("Please use option -u and -s")
        exit()
else:
    if args.maximum_images:
        try:
            args.maximum_images = int(args.maximum_images)
            if args.maximum_images <= 0:
                logging.error("Maximum images must be greater than 0")
                exit()
        except ValueError:
            logging.error("Invalid value for maximum_images: This argument needs to be a number")
            exit()
            
    session = vinted_session()
    download_vinted_data(userids, session)
