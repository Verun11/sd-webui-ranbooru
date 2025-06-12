from io import BytesIO
import html
import random
import requests
import re
import modules.scripts as scripts
import gradio as gr
import os
from PIL import Image
import numpy as np
import importlib
import requests_cache

# New import
from dotenv import load_dotenv

from modules.processing import process_images, StableDiffusionProcessingImg2Img
from modules import shared
from modules.sd_hijack import model_hijack
from modules import deepbooru
from modules.ui_components import InputAccordion

# Load environment variables
load_dotenv()

# Directory and File Setup (Combined and Ensured)
extension_root = scripts.basedir()
user_data_dir = os.path.join(extension_root, 'user')
user_search_dir = os.path.join(user_data_dir, 'search')
user_remove_dir = os.path.join(user_data_dir, 'remove')
user_forbidden_prompt_dir = os.path.join(user_data_dir, 'forbidden_prompt') # From existing
user_wildcards_dir = os.path.join(user_data_dir, 'wildcards') # From existing

os.makedirs(user_search_dir, exist_ok=True)
os.makedirs(user_remove_dir, exist_ok=True)
os.makedirs(user_forbidden_prompt_dir, exist_ok=True) # From existing
os.makedirs(user_wildcards_dir, exist_ok=True) # From existing

# File initializations (Ensuring all are covered, preferring existing forbidden style)
if not os.path.isfile(os.path.join(user_search_dir, 'tags_search.txt')):
    with open(os.path.join(user_search_dir, 'tags_search.txt'), 'w') as f:
        pass
if not os.path.isfile(os.path.join(user_remove_dir, 'tags_remove.txt')):
    with open(os.path.join(user_remove_dir, 'tags_remove.txt'), 'w') as f:
        pass
if not os.path.isfile(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')): # From existing
    with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
        f.write("# Add tags here, one per line\\n")
        f.write("artist_name_example\\n")
        f.write("character_name_example\\n")

# API Auth Constants (From new script)
GEL_API_AUTH, DAN_API_AUTH = '', ''
DANBOORU_TIER = os.getenv("danbooru_tier")
if os.getenv("danbooru_login") and os.getenv("danbooru_api_key"):
    DAN_API_AUTH = f'&login={os.getenv("danbooru_login")}&api_key={os.getenv("danbooru_api_key")}'
if os.getenv("gelbooru_user_id") and os.getenv("gelbooru_api_key"):
    GEL_API_AUTH = f'&user_id={os.getenv("gelbooru_user_id")}&api_key={os.getenv("gelbooru_api_key")}'

# Constants (New/Updated versions)
COLORED_BG = ['black_background', 'aqua_background', 'white_background', 'colored_background', 'gray_background', 'blue_background', 'green_background', 'red_background', 'brown_background', 'purple_background', 'yellow_background', 'orange_background', 'pink_background', 'plain', 'transparent_background', 'simple_background', 'two-tone_background', 'grey_background']
ADD_BG = ['outdoors', 'indoors']
BW_BG = ['monochrome', 'greyscale', 'grayscale']
POST_AMOUNT = 100
COUNT = 100
DEBUG = False
BOORU_ENDPOINTS= {
    "gelbooru": "https://gelbooru.com/index.php?page=post&s=view&id=",
    "rule34": "https://rule34.xxx/index.php?page=post&s=view&id=",
    "safebooru": "https://safebooru.org/index.php?page=post&s=view&id=",
    "danbooru": "https://danbooru.donmai.us/posts/",
    "konachan": "https://konachan.net/post/show/",
    "yande.re": "https://yande.re/post/show/",
    "aibooru": "https://aibooru.online/posts/",
    "xbooru": "https://xbooru.com/index.php?page=post&s=view&id=",
    "e621": "https://e621.net/posts/"
}

RATING_TYPES = {
    "none": {
        "All": "All"
    },
    "full": {
        "All": "All",
        "Safe": "safe",
        "Questionable": "questionable",
        "Explicit": "explicit"
    },
    "single": {
        "All": "All",
        "Safe": "g",
        "Sensitive": "s",
        "Questionable": "q",
        "Explicit": "e"
    }
}
RATINGS = {
    "e621": RATING_TYPES['full'],
    "danbooru": RATING_TYPES['single'],
    "aibooru": RATING_TYPES['full'],
    "yande.re": RATING_TYPES['full'],
    "konachan": RATING_TYPES['full'],
    "safebooru": RATING_TYPES['none'],
    "rule34": RATING_TYPES['full'],
    "xbooru": RATING_TYPES['full'],
    "gelbooru": RATING_TYPES['single']
}

def get_available_ratings(booru):
    mature_ratings = gr.Radio.update(choices=RATINGS[booru].keys(), value="All")
    return mature_ratings


def show_fringe_benefits(booru):
    if booru == 'gelbooru':
        return gr.Checkbox.update(visible=True)
    else:
        return gr.Checkbox.update(visible=False)


def check_exception(booru, parameters):
    post_id = parameters.get('post_id')
    tags = parameters.get('tags')
    if booru == 'konachan' and post_id:
        raise Exception("Konachan does not support post IDs")
    if booru == 'yande.re' and post_id:
        raise Exception("Yande.re does not support post IDs")
    if booru == 'e621' and post_id:
        raise Exception("e621 does not support post IDs")
    # Combined logic: new script checks DANBOORU_TIER, old script checks tag length. Both are important.
    if booru == 'danbooru' and tags and len(tags.split(',')) > 1 and (DANBOORU_TIER is None or DANBOORU_TIER == 'member'):
        raise Exception("Danbooru free/member tier does not support multiple tags. You can have only one tag. Gold/Platinum tier is required for multiple tags.")


class Booru():

    def __init__(self, booru, booru_url):
        self.booru = booru
        self.booru_url = booru_url
        self.headers = {'user-agent': 'my-app/0.0.1'}

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        pass

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        pass


class Gelbooru(Booru):

    def __init__(self, fringe_benefits):
        super().__init__('gelbooru', f'https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}{GEL_API_AUTH}')
        self.fringeBenefits = fringe_benefits

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        for loop in range(2):
            if id:
                add_tags = ''
            # Construct base URL without pid for Gelbooru as per new logic
            base_url_for_request = f'https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}{GEL_API_AUTH}'
            self.booru_url = f"{base_url_for_request}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"

            if self.fringeBenefits:
                res = requests.get(self.booru_url, cookies={'fringeBenefits': 'yup'})
            else:
                res = requests.get(self.booru_url)

            data = {} # Default to empty dict
            try:
                data = res.json()
                # Ensure data is a dictionary, Gelbooru returns an object which res.json() should parse to dict
                if not isinstance(data, dict):
                    print(f"Warning: Gelbooru API did not return a JSON object as expected. Response: {res.text[:200]}")
                    data = {} # Reset to empty if not a dict
                    COUNT = 0
                else:
                    # Safely access attributes
                    attributes = data.get('@attributes', {})
                    COUNT = attributes.get('count', 0)
                    # Ensure COUNT is an integer
                    if not isinstance(COUNT, int):
                        try:
                            COUNT = int(COUNT)
                        except ValueError:
                            print(f"Warning: Gelbooru 'count' attribute is not an integer: {COUNT}. Setting to 0.")
                            COUNT = 0
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: Gelbooru API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0 # No data to count
                data = {} # Ensure data is an empty dict for consistent return type

            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1 # Ensure max_pages is at least 1
                if loop_msg: # Corrected from while to if
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return data

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        # Gelbooru's get_post in the new code calls get_data with "&id=" + id
        # This seems to imply 'id' in get_data is actually the post_id parameter string part
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id if id else "")


class XBooru(Booru):

    def __init__(self):
        super().__init__('xbooru', f'https://xbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        data_posts = [] # Initialize to empty list
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"https://xbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            print(self.booru_url)
            res = requests.get(self.booru_url)

            try:
                raw_data = res.json()
                # XBooru returns a list directly, or sometimes a dict with a 'post' key if it's an error/empty
                if isinstance(raw_data, dict) and 'post' in raw_data : # Check if it's dict and has 'post'
                    data_posts = raw_data['post'] if isinstance(raw_data['post'], list) else []
                elif isinstance(raw_data, list):
                    data_posts = raw_data
                else:
                    print(f"Warning: XBooru API did not return a list or expected dict. Response: {res.text[:200]}")
                    data_posts = []

                COUNT = 0
                for post_idx, post in enumerate(data_posts):
                    if not isinstance(post, dict): # Skip if post is not a dict
                        print(f"Warning: Post at index {post_idx} is not a dictionary, skipping.")
                        continue
                    # Safely construct file_url
                    directory = post.get('directory')
                    image_name = post.get('image')
                    if directory and image_name:
                        post['file_url'] = f"https://xbooru.com/images/{directory}/{image_name}"
                    else:
                        post['file_url'] = "" # Default if parts are missing
                    COUNT += 1
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: XBooru API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_posts = []


            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return {'post': data_posts} # Ensure 'post' key exists

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id if id else "")


class Rule34(Booru):

    def __init__(self):
        super().__init__('rule34', f'https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        data_posts = []
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)

            try:
                raw_data = res.json()
                # Rule34 returns a list or null/empty on no results
                if isinstance(raw_data, list):
                    data_posts = raw_data
                else: # Handles null or other non-list responses
                    data_posts = []
                COUNT = len(data_posts)
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: Rule34 API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_posts = []

            if COUNT == 0: # Changed from `COUNT <= max_pages*POST_AMOUNT` as per new logic for Rule34
                max_pages = 2
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results") # Kept from new logic
            break
        return {'post': data_posts}

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id if id else "")


class Safebooru(Booru):

    def __init__(self):
        super().__init__('safebooru', f'https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        data_posts = []
        for loop in range(2):
            if id:
                add_tags = ''
            self.booru_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}&pid={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)

            try:
                raw_data = res.json()
                # Safebooru returns a list.
                if isinstance(raw_data, list):
                    data_posts = raw_data
                else:
                    print(f"Warning: Safebooru API did not return a list. Response: {res.text[:200]}")
                    data_posts = []

                COUNT = 0
                for post_idx, post in enumerate(data_posts):
                    if not isinstance(post, dict):
                        print(f"Warning: Safebooru post at index {post_idx} is not a dictionary, skipping.")
                        continue
                    directory = post.get('directory')
                    image_name = post.get('image')
                    if directory and image_name:
                        post['file_url'] = f"https://safebooru.org/images/{directory}/{image_name}"
                    else:
                        post['file_url'] = ""
                    COUNT += 1
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: Safebooru API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_posts = []

            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return {'post': data_posts}

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        return self.get_data(add_tags, user_tagged, max_pages, "&id=" + id if id else "")


class Konachan(Booru):

    def __init__(self):
        super().__init__('konachan', f'https://konachan.com/post.json?limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        data_posts = []
        for loop in range(2):
            if id: # Konachan does not use `id` for general search, but this might be for post ID later
                add_tags = ''
            # Konachan uses 'page' not 'pid'
            self.booru_url = f"https://konachan.com/post.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)

            try:
                raw_data = res.json()
                if isinstance(raw_data, list):
                    data_posts = raw_data
                else:
                    data_posts = []
                COUNT = len(data_posts)
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: Konachan API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_posts = []

            if COUNT == 0: # Logic from new script
                max_pages = 2
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data_posts}

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        raise Exception("Konachan does not support post IDs") # As per new script


class Yandere(Booru): # Name kept as Yandere from new script

    def __init__(self):
        super().__init__('yande.re', f'https://yande.re/post.json?limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        data_posts = []
        for loop in range(2):
            if id:
                add_tags = ''
            # Yande.re uses 'page' not 'pid'
            self.booru_url = f"https://yande.re/post.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url)

            try:
                raw_data = res.json()
                if isinstance(raw_data, list):
                    data_posts = raw_data
                else:
                    data_posts = []
                COUNT = len(data_posts)
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: Yande.re API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_posts = []

            if COUNT == 0: # Logic from new script
                max_pages = 2
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data_posts}

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        raise Exception("Yande.re does not support post IDs") # As per new script


class AIBooru(Booru):

    def __init__(self):
        # Corrected class name from 'AIBooru' to 'aibooru' to match dropdown and RATINGS keys
        super().__init__('aibooru', f'https://aibooru.online/posts.json?limit={POST_AMOUNT}')


    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        data_posts = []
        for loop in range(2):
            if id:
                add_tags = ''
            # AIBooru uses 'page'
            self.booru_url = f"https{self.booru_url.split('https')[1]}&page={random.randint(0, max_pages-1)}{id}{add_tags}" # Ensure base URL is correct
            res = requests.get(self.booru_url)

            try:
                raw_data = res.json()
                if isinstance(raw_data, list):
                    data_posts = raw_data
                    for post_idx, post in enumerate(data_posts):
                        if not isinstance(post, dict):
                            print(f"Warning: AIBooru post at index {post_idx} is not a dictionary, skipping.")
                            continue
                        post['tags'] = post.get('tag_string', '') # New script logic
                else:
                    data_posts = []
                COUNT = len(data_posts)
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: AIBooru API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_posts = []

            if COUNT == 0: # Logic from new script
                max_pages = 2
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data_posts}

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        # Original new code raised exception. If specific post fetching is needed, it would be:
        # self.booru_url = f"https://aibooru.online/posts/{id}.json"
        # For now, keeping with "does not support post IDs" from new script's pattern for this type of API
        raise Exception("AIBooru does not support fetching single posts by ID in this context")


class Danbooru(Booru):

    def __init__(self):
        super().__init__('danbooru', f'https://danbooru.donmai.us/posts.json?limit={POST_AMOUNT}{DAN_API_AUTH}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        # Tier logic from new script
        if (DANBOORU_TIER == 'gold' or DANBOORU_TIER == 'platinum') and not user_tagged : # Modified: user_tagged is False
            max_pages = max_pages * 50
        else:
            max_pages = max_pages * 5 # Free/Basic/Gold+ with search tags limit page differently

        global COUNT
        loop_msg = True
        data_posts = []
        for loop in range(2):
            if id: # For specific post ID, tags are usually ignored by API endpoint for single post
                add_tags = ''
            # Danbooru uses 'page'
            self.booru_url = f"https://danbooru.donmai.us/posts.json?limit={POST_AMOUNT}{DAN_API_AUTH}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)

            try:
                raw_data = res.json()
                if isinstance(raw_data, list):
                    data_posts = raw_data
                    for post_idx, post in enumerate(data_posts):
                        if not isinstance(post, dict):
                            print(f"Warning: Danbooru post at index {post_idx} is not a dictionary, skipping.")
                            continue
                        post['tags'] = post.get('tag_string', '') # New script logic
                else: # Handles errors or empty results not being a list
                    data_posts = []
                COUNT = len(data_posts)
            except requests.exceptions.JSONDecodeError:
                print(f"Warning: Danbooru API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_posts = []

            if COUNT == 0: # Logic from new script
                max_pages = 2
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f"Found enough results")
            break
        return {'post': data_posts}

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        if not id:
            raise Exception("Post ID is required for Danbooru get_post")
        self.booru_url = f"https://danbooru.donmai.us/posts/{id}.json{DAN_API_AUTH}" # Auth might be needed
        res = requests.get(self.booru_url, headers=self.headers)
        data = {}
        try:
            data = res.json()
            if isinstance(data, dict) and data.get('id'): # Check if it's a valid post
                 data['tags'] = data.get('tag_string', '')
                 return {'post': [data]} # Return as list item
            else: # Handle cases where post is not found or error
                print(f"Danbooru get_post for ID {id} failed or returned unexpected data: {res.text[:200]}")
                return {'post': []}
        except requests.exceptions.JSONDecodeError:
            print(f"Danbooru get_post for ID {id} returned non-JSON: {res.text[:200]}")
            return {'post': []}


class e621(Booru):

    def __init__(self):
        # Corrected super().__init__ call to use 'e621' as booru name
        super().__init__('e621', f'https://e621.net/posts.json?limit={POST_AMOUNT}')

    def get_data(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        global COUNT
        loop_msg = True
        data_list = [] # e621 returns {'posts': [...]}
        for loop in range(2):
            if id: # For specific post ID, tags are usually ignored by API endpoint for single post
                add_tags = ''
            # e621 uses 'page'
            self.booru_url = f"https://e621.net/posts.json?limit={POST_AMOUNT}&page={random.randint(0, max_pages-1)}{id}{add_tags}"
            res = requests.get(self.booru_url, headers=self.headers)

            try:
                json_response = res.json()
                # Data is in json_response['posts']
                data_list = json_response.get('posts', []) if isinstance(json_response, dict) else []
                if not isinstance(data_list, list): # Ensure it's a list
                    print(f"Warning: e621 API 'posts' field was not a list. Response: {str(json_response)[:200]}")
                    data_list = []

                COUNT = len(data_list) # Count is length of the 'posts' list
                for post_idx, post_item in enumerate(data_list):
                    if not isinstance(post_item, dict):
                        print(f"Warning: e621 post at index {post_idx} is not a dictionary, skipping.")
                        continue
                    temp_tags = []
                    # New script logic for tags and score
                    sublevels = ['general', 'artist', 'copyright', 'character', 'species']
                    for sublevel in sublevels:
                        temp_tags.extend(post_item.get('tags', {}).get(sublevel, []))
                    post_item['tags'] = ' '.join(temp_tags)
                    post_item['score'] = post_item.get('score', {}).get('total', 0)

            except requests.exceptions.JSONDecodeError:
                print(f"Warning: e621 API response was not valid JSON. Response: {res.text[:200]}")
                COUNT = 0
                data_list = []

            # Logic from new script for COUNT and max_pages
            if COUNT <= max_pages*POST_AMOUNT:
                max_pages = (COUNT // POST_AMOUNT) + 1 if COUNT > 0 else 1
                if loop_msg:
                    print(f" Processing {COUNT} results.")
                    loop_msg = False
                continue
            else:
                print(f" Processing {max_pages*POST_AMOUNT} out of {COUNT} results.")
            break
        return {'post': data_list} # Return the list under 'post' key

    def get_post(self, add_tags, user_tagged, max_pages=10, id=''): # Added user_tagged
        # New script had: self.get_data(add_tags, user_tagged, max_pages, "&id=" + id)
        # This is unusual for e621, which typically uses /posts/{id}.json
        # Let's implement direct post fetching if ID is provided.
        if not id:
             raise Exception("Post ID is required for e621 get_post")

        # Construct the direct URL for fetching a single post by ID
        self.booru_url = f"https://e621.net/posts/{id}.json"
        res = requests.get(self.booru_url, headers=self.headers)
        try:
            json_response = res.json()
            post_data = json_response.get('post') if isinstance(json_response, dict) else None

            if isinstance(post_data, dict):
                temp_tags = []
                sublevels = ['general', 'artist', 'copyright', 'character', 'species']
                for sublevel in sublevels:
                    temp_tags.extend(post_data.get('tags', {}).get(sublevel, []))
                post_data['tags'] = ' '.join(temp_tags)
                post_data['score'] = post_data.get('score', {}).get('total', 0)
                # Ensure 'file_url' exists, e621 uses post_data['file']['url']
                if 'file' in post_data and 'url' in post_data['file']:
                    post_data['file_url'] = post_data['file']['url']
                else:
                    post_data['file_url'] = None # Or some default placeholder

                return {'post': [post_data]} # Return as a list item
            else:
                print(f"e621 get_post for ID {id} did not return a valid post structure: {res.text[:200]}")
                return {'post': []}
        except requests.exceptions.JSONDecodeError:
            print(f"e621 get_post for ID {id} returned non-JSON: {res.text[:200]}")
            return {'post': []}


def generate_chaos(pos_tags, neg_tags, chaos_amount):
    """Generates chaos in the prompt by adding random tags from the prompt to the positive and negative prompts

    Args:
        pos_tags (str): the positive prompt
        neg_tags (str): the negative prompt
        chaos_amount (float): the percentage of tags to put in the positive prompt

    Returns:
        str: the positive prompt
        str: the negative prompt
    """
    # create a list with the tags in the prompt and in the negative prompt
    chaos_list = [tag for tag in pos_tags.split(',') + neg_tags.split(',') if tag.strip() != '']
    # distinct the list
    chaos_list = list(set(chaos_list))
    random.shuffle(chaos_list)
    # put chaos_amount % of the tags in the negative prompt and the remaining in the positive prompt
    len_list = round(len(chaos_list) * chaos_amount) # Tags for negative
    neg_list = chaos_list[:len_list]
    random.shuffle(neg_list) # Shuffle negative again for good measure
    neg_prompt = ','.join(neg_list)

    pos_list = chaos_list[len_list:] # Tags for positive
    pos_prompt = ','.join(pos_list)
    return pos_prompt, neg_prompt


def resize_image(img, width, height, cropping=True):
    """Resize image to specified width and height

    Args:
        img (PIL.Image): the image
        width (int): the width in pixels
        height (int): the height in pixels
        cropping (bool): whether to crop the image or not

    Returns:
        PIL.Image: the resized image
    """
    if cropping:
        # resize the picture and center crop it
        # example: you have a 100x200 picture and width=300 and height=300
        # resize to 300x600 and crop to 300x300 from the center
        x, y = img.size
        img_new_size_w, img_new_size_h = x, y # Assign initial values

        if x < y: # Portrait or square image that needs scaling to width first
            wpercent = (width / float(x))
            hsize = int((float(y) * float(wpercent)))
            img_new = img.resize((width, hsize))
            img_new_size_w, img_new_size_h = img_new.size
            # Check if after scaling to width, height is still less than target, then scale to height
            if img_new_size_h < height:
                hpercent = (height / float(img_new_size_h)) # Use new height for percentage
                wsize_final = int((float(img_new_size_w) * float(hpercent)))
                img_new = img_new.resize((wsize_final, height))
        else: # Landscape or square image that needs scaling to height first
            hpercent = (height / float(y))
            wsize = int((float(x) * float(hpercent)))
            img_new = img.resize((wsize, height))
            img_new_size_w, img_new_size_h = img_new.size
            # Check if after scaling to height, width is still less than target, then scale to width
            if img_new_size_w < width:
                wpercent = (width / float(img_new_size_w)) # Use new width for percentage
                hsize_final = int((float(img_new_size_h) * float(wpercent)))
                img_new = img_new.resize((width, hsize_final))

        # Recalculate crop box based on the final scaled image (img_new)
        x_crop, y_crop = img_new.size
        left = (x_crop - width) / 2
        top = (y_crop - height) / 2
        right = (x_crop + width) / 2
        bottom = (y_crop + height) / 2
        img = img_new.crop((left, top, right, bottom))
    else:
        img = img.resize((width, height))
    return img

def modify_prompt(prompt, tagged_prompt, type_deepbooru):
    """Modifies the prompt based on the type_deepbooru selected

    Args:
        prompt (str): the prompt
        tagged_prompt (str): the prompt tagged by deepbooru
        type_deepbooru (str): the type of modification

    Returns:
        str: the modified prompt
    """
    if type_deepbooru == 'Add Before':
        return tagged_prompt + ',' + prompt if prompt else tagged_prompt # Handle empty prompt
    elif type_deepbooru == 'Add After':
        return prompt + ',' + tagged_prompt if prompt else tagged_prompt # Handle empty prompt
    elif type_deepbooru == 'Replace':
        return tagged_prompt
    return prompt

def remove_repeated_tags(prompt):
    """Removes the repeated tags keeping the same order

    Args:
        prompt (str): the prompt

    Returns:
        str: the prompt without repeated tags
    """
    if not prompt: return "" # Handle empty prompt
    prompt_parts = prompt.split(',')
    new_prompt_parts = []
    seen_tags = set() # Keep track of tags already added
    for tag_part in prompt_parts:
        stripped_tag = tag_part.strip()
        if stripped_tag and stripped_tag not in seen_tags:
            new_prompt_parts.append(stripped_tag)
            seen_tags.add(stripped_tag)
        elif not stripped_tag: # Keep empty parts if they were intentional (e.g. ",,") but usually not.
             new_prompt_parts.append("") # Or decide to filter them out completely
    return ','.join(new_prompt_parts)

def limit_prompt_tags(prompt, limit_tags_val, mode): # Renamed limit_tags to limit_tags_val
    """Limits the amount of tags in the prompt. It can be done by percentage or by a fixed amount.

    Args:
        prompt (str): the prompt
        limit_tags_val (float or int): the percentage of tags to keep (if mode is 'Limit') or max number of tags (if mode is 'Max')
        mode (str): 'Limit' or 'Max'

    Returns:
        str: the prompt with the limited amount of tags
    """
    if not prompt: return ""
    clean_prompt_parts = [tag.strip() for tag in prompt.split(',') if tag.strip()] # Split and strip empty

    if mode == 'Limit': # Percentage based
        # Ensure limit_tags_val is float for percentage
        limit_val = float(limit_tags_val)
        num_to_keep = int(len(clean_prompt_parts) * limit_val)
        clean_prompt_parts = clean_prompt_parts[:num_to_keep]
    elif mode == 'Max': # Fixed amount
        # Ensure limit_tags_val is int for max count
        max_val = int(limit_tags_val)
        clean_prompt_parts = clean_prompt_parts[:max_val]

    return ','.join(clean_prompt_parts)


class Script(scripts.Script):
    # previous_loras, last_img, real_steps, version, original_prompt are key.
    # result_url, result_img from new script are OMITTED (part of 'get last result' UI)
    previous_loras = ''
    last_img = []
    real_steps = 0
    version = "1.2" # Or keep existing if preferred, new one is "1.2"
    original_prompt = ''

    # Attributes to be set in before_process for postprocess to use (as UI args not passed directly)
    use_img2img_flag = False
    use_ip_flag = False
    enabled_flag = False
    denoising_strength = 0.75
    use_deepbooru_flag = False
    type_deepbooru_val = "Add Before"
    crop_center_flag = False
    use_last_img_flag = False

    def process_wildcards(self, current_tags_string):
        import re; import os; import random
        processed_tags = current_tags_string
        while True:
            match = re.search(r'__([a-zA-Z0-9_]+)__', processed_tags)
            if not match: break
            keyword = match.group(1); wildcard_to_replace = match.group(0); replacement_tag = ""
            file_path = os.path.join(user_wildcards_dir, f"{keyword}.txt")
            if os.path.exists(file_path) and os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        possible_tags = [line.strip() for line in f if line.strip()]
                    if possible_tags: replacement_tag = random.choice(possible_tags)
                except Exception as e: print(f"[Ranbooru] Error reading wildcard file {file_path}: {e}")
            processed_tags = processed_tags.replace(wildcard_to_replace, replacement_tag, 1)
        return ','.join([tag.strip() for tag in processed_tags.split(',') if tag.strip()])

    def get_files(self, path):
        files = [];
        if os.path.exists(path): # Check if path exists
            for file in os.listdir(path):
                if file.endswith('.txt'): files.append(file)
        return files

    def refresh_ser(self): return gr.update(choices=self.get_files(user_search_dir))

    def refresh_rem(self): return gr.update(choices=self.get_files(user_remove_dir))

    def get_forbidden_files(self):
        os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
        files = [f for f in os.listdir(user_forbidden_prompt_dir) if f.endswith('.txt')]
        default_file = 'tags_forbidden.txt' # Renamed
        default_file_path = os.path.join(user_forbidden_prompt_dir, default_file) # Renamed
        if not files and not os.path.exists(default_file_path):
            with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\nartist_name_example\ncharacter_name_example\n")
            files.append(default_file)
        elif default_file not in files and not os.path.exists(default_file_path): # Check if default not in files list
             with open(default_file_path, 'w') as f: f.write("# Add tags here, one per line\nartist_name_example\ncharacter_name_example\n")
        if default_file not in files and os.path.exists(default_file_path): files.append(default_file)
        return files if files else [default_file]

    def refresh_forbidden_files(self): return gr.update(choices=self.get_forbidden_files())

    def title(self): return "Ranbooru"

    def show(self, is_img2img): return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with InputAccordion(False, label="Ranbooru", elem_id=self.elem_id("ra_enable")) as enabled:
            booru = gr.Dropdown(["gelbooru", "rule34", "safebooru", "danbooru", "konachan", 'yande.re', 'aibooru', 'xbooru', 'e621'], label="Booru", value="gelbooru")
            max_pages = gr.Slider(label="Max Pages", minimum=1, maximum=100, value=100, step=1)
            gr.Markdown("""## Post"""); post_id = gr.Textbox(lines=1, label="Post ID")
            gr.Markdown("""## Tags""")
            tags = gr.Textbox(lines=1, label="Tags to Search (Pre)", info="Use __wildcard__ to pick a random tag from user/wildcards/wildcard.txt")
            remove_tags = gr.Textbox(lines=1, label="Tags to Remove (Post)")
            mature_rating = gr.Radio(list(RATINGS.get('gelbooru', {}).keys()), label="Mature Rating", value="All") # Safe get
            remove_bad_tags = gr.Checkbox(label="Remove bad tags", value=True); shuffle_tags = gr.Checkbox(label="Shuffle tags", value=True)
            change_dash = gr.Checkbox(label='Convert "_" to spaces', value=False); same_prompt = gr.Checkbox(label="Use same prompt for all images", value=False)
            fringe_benefits = gr.Checkbox(label="Fringe Benefits", value=True, visible=(booru.value == "gelbooru")) # Visibility based on initial value
            limit_tags = gr.Slider(value=1.0, label="Limit tags", minimum=0.05, maximum=1.0, step=0.05)
            max_tags_slider = gr.Slider(value=100, label="Max tags", minimum=1, maximum=100, step=1) # Renamed variable
            change_background = gr.Radio(["Don't Change", "Add Background", "Remove Background", "Remove All"], label="Change Background", value="Don't Change")
            change_color = gr.Radio(["Don't Change", "Colored", "Limited Palette", "Monochrome"], label="Change Color", value="Don't Change")
            sorting_order = gr.Radio(["Random", "High Score", "Low Score"], label="Sorting Order", value="Random")
            disable_prompt_modification = gr.Checkbox(label="Disable Ranbooru prompt modification", value=False)
            booru.change(get_available_ratings, booru, mature_rating)
            booru.change(show_fringe_benefits, booru, fringe_benefits)
            gr.Markdown("""\n---\n"""); gr.Markdown("### Post-Fetch Prompt Tag Filtering")
            forbidden_prompt_tags_text = gr.Textbox(lines=2, label="Forbidden Prompt Tags (Manual Input)", info="Comma-separated. Tags to remove from prompt AFTER image selection.")
            use_forbidden_prompt_txt = gr.Checkbox(label="Use Forbidden Prompt Tags from file", value=False)
            choose_forbidden_prompt_txt = gr.Dropdown(self.get_forbidden_files(), label="Choose Forbidden Prompt Tags .txt file", value="tags_forbidden.txt")
            forbidden_refresh_btn = gr.Button("Refresh Forbidden Files"); gr.Markdown("""\n---\n""")
            with gr.Group():
                with gr.Accordion("Img2Img", open=False):
                    use_img2img = gr.Checkbox(label="Use img2img", value=False); use_ip = gr.Checkbox(label="Send to Controlnet", value=False)
                    denoising = gr.Slider(value=0.75, label="Denoising", minimum=0.05, maximum=1.0, step=0.05)
                    use_last_img = gr.Checkbox(label="Use last image as img2img", value=False); crop_center = gr.Checkbox(label="Crop Center", value=False)
                    use_deepbooru = gr.Checkbox(label="Use Deepbooru", value=False)
                    type_deepbooru = gr.Radio(["Add Before", "Add After", "Replace"], label="Deepbooru Tags Position", value="Add Before")
            with gr.Group():
                with gr.Accordion("File", open=False):
                    use_search_txt = gr.Checkbox(label="Use tags_search.txt", value=False)
                    choose_search_txt = gr.Dropdown(self.get_files(user_search_dir), label="Choose tags_search.txt", value="")
                    search_refresh_btn = gr.Button("Refresh")
                    use_remove_txt = gr.Checkbox(label="Use tags_remove.txt", value=False)
                    choose_remove_txt = gr.Dropdown(self.get_files(user_remove_dir), label="Choose tags_remove.txt", value="")
                    remove_refresh_btn = gr.Button("Refresh")
            with gr.Group():
                with gr.Accordion("Extra", open=False):
                    with gr.Box(): mix_prompt = gr.Checkbox(label="Mix prompts", value=False); mix_amount = gr.Slider(value=2, label="Mix amount", minimum=2, maximum=10, step=1)
                    with gr.Box(): chaos_mode = gr.Radio(["None", "Chaos", "Less Chaos"], label="Chaos Mode", value="None"); chaos_amount = gr.Slider(value=0.5, label="Chaos Amount %", minimum=0.1, maximum=1, step=0.05)
                    with gr.Box(): negative_mode = gr.Radio(["None", "Negative"], label="Negative Mode", value="None"); use_same_seed = gr.Checkbox(label="Use same seed for all pictures", value=False)
                    with gr.Box(): use_cache = gr.Checkbox(label="Use cache", value=True)
        with InputAccordion(False, label="LoRAnado", elem_id=self.elem_id("lo_enable")) as lora_enabled_ui: # Renamed
            with gr.Box():
                lora_lock_prev = gr.Checkbox(label="Lock previous LoRAs", value=False); lora_folder = gr.Textbox(lines=1, label="LoRAs Subfolder")
                lora_amount = gr.Slider(value=1, label="LoRAs Amount", minimum=1, maximum=10, step=1)
            with gr.Box():
                lora_min = gr.Slider(value=-1.0, label="Min LoRAs Weight", minimum=-1.0, maximum=1, step=0.1)
                lora_max = gr.Slider(value=1.0, label="Max LoRAs Weight", minimum=-1.0, maximum=1.0, step=0.1)
                lora_custom_weights = gr.Textbox(lines=1, label="LoRAs Custom Weights")
        search_refresh_btn.click(fn=self.refresh_ser, inputs=[], outputs=[choose_search_txt])
        remove_refresh_btn.click(fn=self.refresh_rem, inputs=[], outputs=[choose_remove_txt])
        forbidden_refresh_btn.click(fn=self.refresh_forbidden_files, inputs=[], outputs=[choose_forbidden_prompt_txt])
        return [enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags_slider, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled_ui, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification]

    def hide_object(self, obj, booru_val): # Renamed booru to booru_val
        print(f'hide_object: {obj}, {booru_val}') # Use new name
        if booru_val == 'konachan' or booru_val == 'yande.re': obj.interactive = False
        else: obj.interactive = True

    def check_orientation(self, img):
        """Check if image is portrait, landscape or square"""
        x, y = img.size
        if x / y > 1.2: # Landscape
            return [768, 512]
        elif y / x > 1.2: # Portrait
            return [512, 768]
        else: # Square-ish
            return [768, 768] # Or p.width, p.height if available contextually

    def loranado(self, lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev):
        lora_prompt = ''
        if lora_enabled:
            if lora_lock_prev:
                lora_prompt = self.previous_loras
            else:
                loras = []
                # Path logic from existing script is better:
                loras_path = os.path.join(shared.cmd_opts.lora_dir, lora_folder) if hasattr(shared, 'cmd_opts') and hasattr(shared.cmd_opts, 'lora_dir') and lora_folder else shared.cmd_opts.lora_dir if hasattr(shared, 'cmd_opts') and hasattr(shared.cmd_opts, 'lora_dir') else f'models/Lora/{lora_folder}'

                if not os.path.exists(loras_path):
                    print(f"[Ranbooru] LoRA folder not found: {loras_path}")
                    self.previous_loras = "" # Reset if folder not found
                    return p

                # Ensure loras_path is a directory
                if not os.path.isdir(loras_path):
                    print(f"[Ranbooru] LoRA path is not a directory: {loras_path}")
                    self.previous_loras = ""
                    return p

                try:
                    loras = os.listdir(loras_path)
                    loras = [lora.replace('.safetensors', '').replace('.pt', '').replace('.ckpt', '') for lora in loras if lora.endswith(('.safetensors', '.pt', '.ckpt'))]
                except Exception as e:
                    print(f"[Ranbooru] Error reading LoRAs from {loras_path}: {e}")
                    loras = []

                if not loras:
                    print(f"[Ranbooru] No LoRAs found in {loras_path}")
                    self.previous_loras = "" # Reset if no LoRAs found
                    return p

                selected_loras_for_prompt = []
                for i in range(0, lora_amount):
                    lora_weight = 0.0 # Default to float
                    custom_weights_list = [w.strip() for w in lora_custom_weights.split(',') if w.strip()]

                    if lora_custom_weights != '' and i < len(custom_weights_list):
                        try:
                            lora_weight = float(custom_weights_list[i])
                        except ValueError:
                            print(f"[Ranbooru] Invalid LoRA weight '{custom_weights_list[i]}', using random.")
                            lora_weight = round(random.uniform(lora_min, lora_max), 2) # Use more precision
                    else:
                        lora_weight = round(random.uniform(lora_min, lora_max), 2)

                    # Ensure weight is not 0 unless min and max are both 0
                    if lora_weight == 0.0 and not (lora_min == 0.0 and lora_max == 0.0):
                        if lora_max > 0.0 : lora_weight = round(random.uniform(max(lora_min, 0.01), lora_max), 2) # Try to get non-zero
                        elif lora_min < 0.0 : lora_weight = round(random.uniform(lora_min, min(lora_max, -0.01)), 2)
                        else: lora_weight = 0.1 # A small default if min/max are tricky

                    if loras: # Check again if loras list is not empty
                        selected_loras_for_prompt.append(f'<lora:{random.choice(loras)}:{lora_weight}>')

                lora_prompt = ''.join(selected_loras_for_prompt) # Join without spaces initially
                self.previous_loras = lora_prompt

        if lora_prompt:
            if isinstance(p.prompt, list):
                for num, pr in enumerate(p.prompt):
                    p.prompt[num] = f'{lora_prompt.strip()} {pr.strip()}'.strip() # Ensure clean joining
            else:
                p.prompt = f'{lora_prompt.strip()} {p.prompt.strip()}'.strip()
        return p

    def random_number(self, sorting_order, size):
        """Generates random numbers based on the sorting_order - New Version"""
        global COUNT # Uses global COUNT updated by Booru classes
        # effective_count = COUNT # Max items available from current booru search

        # The new Booru classes set COUNT to the total number of posts found.
        # This random_number function is choosing *indices* for the list of posts returned by get_data.
        # So, the range should be based on the number of posts *actually retrieved*.
        # This means the `sorting_order` parameter, if an int, is the actual list length.

        actual_list_length = 0
        if isinstance(sorting_order, int) :
             actual_list_length = sorting_order
             # print(f"Warning: random_number called with integer for sorting_order. Assuming it's actual_list_length: {actual_list_length}")
        else:
             actual_list_length = min(COUNT, POST_AMOUNT)
             # This branch assumes global COUNT is the length of the list we are choosing from.
             # For safety, this function should ideally be called with the explicit length of the list it's sampling from.
             # The before_process logic will call this with `len(data['post'])` as the first arg.
             # So, the `isinstance(sorting_order, int)` check will make `actual_list_length` correct.
             # The `else` branch here is a fallback if it's called with the string 'Random', 'High Score', etc.
             # In that specific case, relying on global COUNT (set by Booru classes) is the new intended logic.
             # So, if sorting_order is string, then it refers to the UI choice, and we use global COUNT.

        if actual_list_length == 0: return []
        if size <= 0: return []
        size = min(size, actual_list_length)

        random_indices = []
        if isinstance(sorting_order, str) and (sorting_order == 'High Score' or sorting_order == 'Low Score'):
            weights = np.arange(actual_list_length, 0, -1).astype(float)
            weights /= weights.sum()
            try:
                random_indices = np.random.choice(np.arange(actual_list_length), size=size, p=weights, replace=False)
            except ValueError as e:
                 print(f"Error in np.random.choice (weighted): {e}. Falling back to simple random sample.")
                 random_indices = random.sample(range(actual_list_length), size)
        else: # Random sampling (either sorting_order is 'Random' or it was an int list_length)
            random_indices = random.sample(range(actual_list_length), size)

        return list(random_indices)

    def use_autotagger(self, model_name_param):
        """Use the autotagger to tag the images - New version"""
        # model_name_param is 'deepbooru'
        if model_name_param == 'deepbooru' and hasattr(self, 'last_img') and self.last_img:
            num_images = len(self.last_img)
            contextual_prompts = []

            if isinstance(self.original_prompt, str):
                contextual_prompts = [self.original_prompt] * num_images
            elif isinstance(self.original_prompt, list):
                if len(self.original_prompt) == num_images:
                    contextual_prompts = self.original_prompt
                elif len(self.original_prompt) > num_images:
                    contextual_prompts = self.original_prompt[:num_images]
                else:
                    last_orig_prompt = self.original_prompt[-1] if self.original_prompt else ""
                    contextual_prompts = list(self.original_prompt) + [last_orig_prompt] * (num_images - len(self.original_prompt))
            else:
                contextual_prompts = [""] * num_images

            final_tagged_prompts = []
            try:
                print(f"[Ranbooru] Starting DeepBooru tagging for {num_images} images...")
                deepbooru.model.start()
                for i in range(num_images):
                    generated_tags_str = deepbooru.model.tag_multi(self.last_img[i])
                    final_tagged_prompts.append(generated_tags_str) # Return raw tags

                print("[Ranbooru] DeepBooru tagging complete.")
            except Exception as e:
                print(f"[Ranbooru] Error during DeepBooru tagging: {e}")
                final_tagged_prompts = [""] * num_images
            finally:
                if hasattr(deepbooru, 'model') and hasattr(deepbooru.model, 'stop'):
                    deepbooru.model.stop()
            return final_tagged_prompts
        return [""] * len(self.last_img) if hasattr(self, 'last_img') and self.last_img else []

    def before_process(self, enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags_slider, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled_ui, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification, p):
        self.enabled_flag = enabled
        self.use_img2img_flag = use_img2img
        self.use_ip_flag = use_ip
        self.denoising_strength = denoising
        self.use_deepbooru_flag = use_deepbooru
        self.type_deepbooru_val = type_deepbooru
        self.crop_center_flag = crop_center
        self.use_last_img_flag = use_last_img
        self.real_steps = p.steps

        if use_cache and not requests_cache.patcher.is_installed():
            requests_cache.install_cache('ranbooru_cache', backend='sqlite', expire_after=3600)
        elif not use_cache and requests_cache.patcher.is_installed():
            requests_cache.uninstall_cache()

        if not enabled:
            if lora_enabled_ui:
                p = self.loranado(lora_enabled_ui, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)
            return

        if disable_prompt_modification:
            if lora_enabled_ui:
                 p = self.loranado(lora_enabled_ui, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)
            return

        booru_apis = {
            'gelbooru': Gelbooru(fringe_benefits), 'rule34': Rule34(), 'safebooru': Safebooru(),
            'danbooru': Danbooru(), 'konachan': Konachan(), 'yande.re': Yandere(),
            'aibooru': AIBooru(), 'xbooru': XBooru(), 'e621': e621(),
        }
        self.original_prompt = p.prompt

        tags_from_ui_processed_wildcards = self.process_wildcards(tags)

        check_exception(booru, {'tags': tags_from_ui_processed_wildcards, 'post_id': post_id})

        current_bad_tags = []
        if remove_bad_tags:
            current_bad_tags.extend(['mixed-language_text', 'watermark', 'text', 'english_text', 'speech_bubble', 'signature', 'artist_name', 'censored', 'bar_censor', 'translation', 'twitter_username', "twitter_logo", 'patreon_username', 'commentary_request', 'tagme', 'commentary', 'character_name', 'mosaic_censoring', 'instagram_username', 'text_focus', 'english_commentary', 'comic', 'translation_request', 'fake_text', 'translated', 'paid_reward_available', 'thought_bubble', 'multiple_views', 'silent_comic', 'out-of-frame_censoring', 'symbol-only_commentary', '3koma', '2koma', 'character_watermark', 'spoken_question_mark', 'japanese_text', 'spanish_text', 'language_text', 'fanbox_username', 'commission', 'original', 'ai_generated', 'stable_diffusion', 'tagme_(artist)', 'text_bubble', 'qr_code', 'chinese_commentary', 'korean_text', 'partial_commentary', 'chinese_text', 'copyright_request', 'heart_censor', 'censored_nipples', 'page_number', 'scan', 'fake_magazine_cover', 'korean_commentary'])

        if remove_tags:
            current_bad_tags.extend(tag.strip() for tag in remove_tags.split(',') if tag.strip())
        if use_remove_txt and choose_remove_txt:
            try:
                remove_file_path = os.path.join(user_remove_dir, choose_remove_txt)
                if os.path.exists(remove_file_path):
                    with open(remove_file_path, 'r', encoding='utf-8') as f:
                        current_bad_tags.extend(tag.strip() for tag in f.read().split(',') if tag.strip())
            except Exception as e:
                print(f"[Ranbooru] Error reading remove_tags file {choose_remove_txt}: {e}")
        current_bad_tags = list(set(current_bad_tags))

        base_prompt_for_ranbooru = str(p.prompt).strip()

        background_options = {'Add Background': (random.choice(ADD_BG) + ',detailed_background', COLORED_BG),
                              'Remove Background': ('plain_background,simple_background,' + random.choice(COLORED_BG), ADD_BG),
                              'Remove All': ('', COLORED_BG + ADD_BG)}
        if change_background in background_options:
            prompt_addition, tags_to_remove_for_bg = background_options[change_background]
            current_bad_tags.extend(tags_to_remove_for_bg)
            if prompt_addition:
                base_prompt_for_ranbooru = f'{base_prompt_for_ranbooru},{prompt_addition}' if base_prompt_for_ranbooru else prompt_addition

        color_options = {'Colored': (None, BW_BG),
                         'Limited Palette': ('(limited_palette:1.3)', None),
                         'Monochrome': (','.join(BW_BG), BW_BG)}
        if change_color in color_options:
            prompt_addition_color, tags_to_remove_for_color = color_options[change_color]
            if tags_to_remove_for_color: current_bad_tags.extend(tags_to_remove_for_color)
            if prompt_addition_color:
                base_prompt_for_ranbooru = f'{base_prompt_for_ranbooru},{prompt_addition_color}' if base_prompt_for_ranbooru else prompt_addition_color

        base_prompt_for_ranbooru = base_prompt_for_ranbooru.strip(',')

        final_booru_search_tags = tags_from_ui_processed_wildcards
        user_tagged_boolean = bool(final_booru_search_tags and final_booru_search_tags.strip())

        if use_search_txt and choose_search_txt:
            try:
                search_file_path = os.path.join(user_search_dir, choose_search_txt)
                if os.path.exists(search_file_path):
                    with open(search_file_path, 'r', encoding='utf-8') as f:
                        search_tags_content = f.read()
                    split_file_tags = [line.strip() for line in search_tags_content.splitlines() if line.strip()]
                    if split_file_tags:
                        selected_file_tags = random.choice(split_file_tags)
                        final_booru_search_tags = f'{final_booru_search_tags},{selected_file_tags}' if final_booru_search_tags else selected_file_tags
                        user_tagged_boolean = True
            except Exception as e:
                print(f"[Ranbooru] Error reading search_tags file {choose_search_txt}: {e}")
        final_booru_search_tags = final_booru_search_tags.strip(',')

        add_tags_query_param = '&tags=-animated'
        if final_booru_search_tags:
             query_tags = final_booru_search_tags.replace(',', '+').replace(' ', '_')
             add_tags_query_param += f'+{query_tags}'

        if mature_rating != 'All' and booru in RATINGS and mature_rating in RATINGS[booru]:
            add_tags_query_param += f'+rating:{RATINGS[booru][mature_rating]}'

        api_instance = booru_apis.get(booru, Gelbooru(fringe_benefits))
        print(f'[Ranbooru] Using Booru: {booru}')

        fetched_data = {}
        if post_id:
            print(f"[Ranbooru] Fetching post by ID: {post_id} from {booru}")
            fetched_data = api_instance.get_post(add_tags_query_param, user_tagged_boolean, max_pages, post_id)
        else:
            print(f"[Ranbooru] Searching posts on {booru} with tags: '{final_booru_search_tags}' (query part: {add_tags_query_param})")
            fetched_data = api_instance.get_data(add_tags_query_param, user_tagged_boolean, max_pages)

        if hasattr(api_instance, 'booru_url') and api_instance.booru_url:
             print(f"[Ranbooru] API URL (most recent): {api_instance.booru_url}")

        if not isinstance(fetched_data, dict) or 'post' not in fetched_data or not isinstance(fetched_data['post'], list):
            print(f"[Ranbooru] Error: Booru API data is not in expected format. Data: {str(fetched_data)[:300]}")
            fetched_data = {'post': []}

        for post_item_idx, post_item_val in enumerate(fetched_data['post']):
            if not isinstance(post_item_val, dict):
                print(f"[Ranbooru] Warning: Post at index {post_item_idx} is not a dictionary. Skipping score processing for it.")
                continue
            post_item_val['score'] = post_item_val.get('score', 0)
            if 'file_url' not in post_item_val or not post_item_val['file_url']:
                keys_to_check_url = ['sample_url', 'large_file_url', ('file', 'url')]
                found_url = None
                for key_url in keys_to_check_url:
                    try:
                        if isinstance(key_url, tuple): value_url = post_item_val.get(key_url[0], {}).get(key_url[1])
                        else: value_url = post_item_val.get(key_url)
                        if value_url: found_url = value_url; break
                    except KeyError: pass
                post_item_val['file_url'] = found_url if found_url else 'https_pic.re_image'


        if sorting_order == 'High Score':
            fetched_data['post'] = sorted(fetched_data['post'], key=lambda k: k.get('score', 0) if isinstance(k,dict) else 0, reverse=True)
        elif sorting_order == 'Low Score':
            fetched_data['post'] = sorted(fetched_data['post'], key=lambda k: k.get('score', 0) if isinstance(k,dict) else 0)

        num_images_to_generate = p.batch_size * p.n_iter
        ranbooru_source_prompts = []
        self.last_img = []
        preview_image_urls_for_img2img = []

        if not fetched_data['post'] and num_images_to_generate > 0:
            raise Exception("[Ranbooru] No posts found from Booru. Try different tags, increase Max Pages, or check Booru status.")

        actual_fetched_post_count = len(fetched_data['post'])

        indices_to_use = self.random_number(sorting_order, num_images_to_generate) if not post_id and actual_fetched_post_count > 0 else [0] * num_images_to_generate

        indices_to_use = [idx for idx in indices_to_use if idx < actual_fetched_post_count]
        if len(indices_to_use) < num_images_to_generate and actual_fetched_post_count > 0:
            if not indices_to_use:
                 indices_to_use = [0] * num_images_to_generate
            else:
                 indices_to_use.extend([indices_to_use[-1]] * (num_images_to_generate - len(indices_to_use)))
        elif actual_fetched_post_count == 0 and num_images_to_generate > 0:
            dummy_post = {'tags': 'dummy_tags', 'file_url': 'https_pic.re_image', 'id': '0'}
            fetched_data['post'] = [dummy_post] * num_images_to_generate
            indices_to_use = list(range(num_images_to_generate))
            actual_fetched_post_count = num_images_to_generate


        for i in range(num_images_to_generate):
            current_post_index = indices_to_use[i] if not same_prompt else indices_to_use[0]
            current_post_index = min(current_post_index, actual_fetched_post_count -1) if actual_fetched_post_count > 0 else 0

            if actual_fetched_post_count == 0:
                selected_post = {'tags': 'error_no_post_found', 'file_url': 'https_pic.re_image', 'id': 'error'}
            else:
                selected_post = fetched_data['post'][current_post_index]

            if mix_prompt and not same_prompt and not post_id and actual_fetched_post_count > 0:
                temp_tags_for_mix = []
                max_len_for_mix = 0
                for _ in range(mix_amount):
                    mix_idx_list = self.random_number(sorting_order, 1)
                    if not mix_idx_list: continue
                    mix_idx = min(mix_idx_list[0], actual_fetched_post_count - 1)
                    mix_post = fetched_data['post'][mix_idx]
                    if isinstance(mix_post, dict) and 'tags' in mix_post:
                        temp_tags_for_mix.extend(mix_post.get('tags', '').split(' '))
                        max_len_for_mix = max(max_len_for_mix, len(mix_post.get('tags','').split(' ')))

                temp_tags_for_mix = list(set(tag for tag in temp_tags_for_mix if tag))
                num_tags_for_mixed = min(len(temp_tags_for_mix), max(20, max_len_for_mix))
                if len(temp_tags_for_mix) > num_tags_for_mixed:
                    selected_post['tags'] = ' '.join(random.sample(temp_tags_for_mix, num_tags_for_mixed))
                else:
                    selected_post['tags'] = ' '.join(temp_tags_for_mix)

            current_tags_from_booru = selected_post.get('tags', 'fallback_tags')
            current_tags_from_booru = current_tags_from_booru.replace('(', '\\(').replace(')', '\\)')

            tags_list_for_prompt = current_tags_from_booru.split(' ')
            if shuffle_tags:
                random.shuffle(tags_list_for_prompt)

            ranbooru_source_prompts.append(','.join(tags_list_for_prompt))

            if isinstance(selected_post, dict):
                 preview_image_urls_for_img2img.append(selected_post.get('file_url', 'https_pic.re_image'))
            else:
                 preview_image_urls_for_img2img.append('https_pic.re_image_error_post_not_dict')


        if (use_img2img or use_deepbooru) and preview_image_urls_for_img2img:
            urls_to_fetch = [preview_image_urls_for_img2img[indices_to_use[0]]] if use_last_img and indices_to_use else preview_image_urls_for_img2img
            urls_to_fetch = urls_to_fetch[:num_images_to_generate]

            print(f"[Ranbooru] Fetching {len(urls_to_fetch)} image(s) for img2img/DeepBooru...")
            for img_idx, img_url_str in enumerate(urls_to_fetch):
                if not img_url_str or not img_url_str.startswith('http'):
                    print(f"[Ranbooru] Invalid or missing image URL: '{img_url_str}', skipping image {img_idx}.")
                    self.last_img.append(Image.new('RGB', (512,512), 'grey'))
                    continue
                try:
                    img_headers = api_instance.headers if hasattr(api_instance, 'headers') else {'user-agent': 'my-app/0.0.1'}
                    response = requests.get(img_url_str, headers=img_headers, timeout=15)
                    response.raise_for_status()
                    self.last_img.append(Image.open(BytesIO(response.content)))
                except requests.RequestException as e:
                    print(f"[Ranbooru] Error fetching image {img_url_str}: {e}")
                    self.last_img.append(Image.new('RGB', (512,512), 'grey'))
                except Exception as e:
                    print(f"[Ranbooru] Error processing image from {img_url_str}: {e}")
                    self.last_img.append(Image.new('RGB', (512,512), 'grey'))

            if use_last_img and self.last_img:
                self.last_img = [self.last_img[0]] * num_images_to_generate
            elif len(self.last_img) < num_images_to_generate:
                if self.last_img:
                    self.last_img.extend([self.last_img[-1]] * (num_images_to_generate - len(self.last_img)))
                else:
                    self.last_img.extend([Image.new('RGB', (512,512), 'grey')] * (num_images_to_generate - len(self.last_img)))


        cleaned_ranbooru_prompts = []
        for single_ran_prompt in ranbooru_source_prompts:
            prompt_tags_list = [tag.strip() for tag in html.unescape(single_ran_prompt).split(',') if tag.strip()]
            final_tags_for_this_prompt = []
            for tag_item in prompt_tags_list:
                is_bad = False
                for bad_tag_entry in current_bad_tags:
                    if '*' in bad_tag_entry:
                        if bad_tag_entry.replace('*', '') in tag_item: is_bad = True; break
                    elif bad_tag_entry == tag_item:
                        is_bad = True; break
                if not is_bad:
                    final_tags_for_this_prompt.append(tag_item)

            cleaned_str = ','.join(final_tags_for_this_prompt)
            if change_dash:
                cleaned_str = cleaned_str.replace("_", " ")
            cleaned_ranbooru_prompts.append(cleaned_str)

        ranbooru_prompts_after_initial_clean = cleaned_ranbooru_prompts

        forbidden_tags_from_ui_and_file = set()
        if forbidden_prompt_tags_text:
            forbidden_tags_from_ui_and_file.update(t.strip().lower() for t in forbidden_prompt_tags_text.split(',') if t.strip())

        if use_forbidden_prompt_txt and choose_forbidden_prompt_txt:
            try:
                forbidden_file_path = os.path.join(user_forbidden_prompt_dir, choose_forbidden_prompt_txt)
                if os.path.exists(forbidden_file_path):
                    with open(forbidden_file_path, 'r', encoding='utf-8') as f:
                        forbidden_tags_from_ui_and_file.update(line.strip().lower() for line in f if line.strip() and not line.startswith('#'))
            except Exception as e:
                print(f"[Ranbooru] Error reading chosen forbidden tags file {choose_forbidden_prompt_txt}: {e}")

        if forbidden_tags_from_ui_and_file:
            print(f"[Ranbooru] Applying post-fetch forbidden tags: {forbidden_tags_from_ui_and_file}")
            prompts_after_forbidden_filter = []
            for prompt_str_item in ranbooru_prompts_after_initial_clean:
                tags_list_item = [t.strip() for t in prompt_str_item.split(',') if t.strip()]
                kept_tags_item = [t for t in tags_list_item if t.lower() not in forbidden_tags_from_ui_and_file]
                prompts_after_forbidden_filter.append(','.join(kept_tags_item))
            final_ranbooru_prompts_to_use = prompts_after_forbidden_filter
        else:
            final_ranbooru_prompts_to_use = ranbooru_prompts_after_initial_clean

        if len(final_ranbooru_prompts_to_use) < num_images_to_generate:
            if not final_ranbooru_prompts_to_use:
                 final_ranbooru_prompts_to_use = [""] * num_images_to_generate
            else:
                 last_val = final_ranbooru_prompts_to_use[-1]
                 final_ranbooru_prompts_to_use.extend([last_val] * (num_images_to_generate - len(final_ranbooru_prompts_to_use)))
        elif len(final_ranbooru_prompts_to_use) > num_images_to_generate:
             final_ranbooru_prompts_to_use = final_ranbooru_prompts_to_use[:num_images_to_generate]


        combined_prompts_for_processing = []
        for i in range(num_images_to_generate):
            current_ran_prompt = final_ranbooru_prompts_to_use[i]
            if base_prompt_for_ranbooru and current_ran_prompt:
                combined_prompts_for_processing.append(f"{base_prompt_for_ranbooru},{current_ran_prompt}")
            elif current_ran_prompt:
                combined_prompts_for_processing.append(current_ran_prompt)
            else:
                combined_prompts_for_processing.append(base_prompt_for_ranbooru)

        p.prompt = combined_prompts_for_processing
        if len(p.prompt) == 1: p.prompt = p.prompt[0]

        if isinstance(p.prompt, list) and not isinstance(p.negative_prompt, list):
            p.negative_prompt = [p.negative_prompt] * len(p.prompt)
        elif not isinstance(p.prompt, list) and isinstance(p.negative_prompt, list):
            p.negative_prompt = p.negative_prompt[0] if p.negative_prompt else ""


        if chaos_mode == 'Chaos':
            if isinstance(p.prompt, list):
                new_prompts_list = []
                new_neg_prompts_list = []
                for idx_chaos, single_prompt_chaos in enumerate(p.prompt):
                    current_neg_for_chaos = p.negative_prompt[idx_chaos] if isinstance(p.negative_prompt, list) else p.negative_prompt
                    transformed_prompt, chaos_neg = generate_chaos(single_prompt_chaos, current_neg_for_chaos, chaos_amount)
                    new_prompts_list.append(transformed_prompt)
                    new_neg_prompts_list.append(f"{current_neg_for_chaos},{chaos_neg}".strip(','))
                p.prompt = new_prompts_list
                p.negative_prompt = new_neg_prompts_list
            else:
                p.prompt, chaos_neg = generate_chaos(p.prompt, p.negative_prompt, chaos_amount)
                p.negative_prompt = f"{p.negative_prompt},{chaos_neg}".strip(',')

        elif chaos_mode == 'Less Chaos':
            if isinstance(p.prompt, list):
                new_prompts_list = []
                new_neg_prompts_list = []
                for idx_chaos, single_prompt_chaos in enumerate(p.prompt):
                    current_neg_for_chaos = p.negative_prompt[idx_chaos] if isinstance(p.negative_prompt, list) else p.negative_prompt
                    transformed_prompt, chaos_neg = generate_chaos(single_prompt_chaos, "", chaos_amount)
                    new_prompts_list.append(transformed_prompt)
                    new_neg_prompts_list.append(f"{current_neg_for_chaos},{chaos_neg}".strip(','))
                p.prompt = new_prompts_list
                p.negative_prompt = new_neg_prompts_list
            else:
                p.prompt, chaos_neg = generate_chaos(p.prompt, "", chaos_amount)
                p.negative_prompt = f"{p.negative_prompt},{chaos_neg}".strip(',')

        if negative_mode == 'Negative':
            if isinstance(p.prompt, list):
                new_pos_prompts_negmode = []
                new_neg_prompts_negmode = []
                current_neg_prompts_base = p.negative_prompt if isinstance(p.negative_prompt,list) else [p.negative_prompt]*len(p.prompt)

                for idx_negmode, full_prompt_item in enumerate(p.prompt):
                    original_tags_set = set(t.strip().lower() for t in self.original_prompt.split(',') if t.strip())
                    current_prompt_tags_list = [t.strip() for t in full_prompt_item.split(',') if t.strip()]

                    derived_tags_for_neg = [t for t in current_prompt_tags_list if t.lower() not in original_tags_set]

                    new_pos_prompts_negmode.append(self.original_prompt)
                    additional_neg_text = ','.join(derived_tags_for_neg)
                    new_neg_prompts_negmode.append(f"{current_neg_prompts_base[idx_negmode]},{additional_neg_text}".strip(','))
                p.prompt = new_pos_prompts_negmode
                p.negative_prompt = new_neg_prompts_negmode
            else:
                original_tags_set = set(t.strip().lower() for t in self.original_prompt.split(',') if t.strip())
                current_prompt_tags_list = [t.strip() for t in p.prompt.split(',') if t.strip()]
                derived_tags_for_neg = [t for t in current_prompt_tags_list if t.lower() not in original_tags_set]

                p.prompt = self.original_prompt
                additional_neg_text = ','.join(derived_tags_for_neg)
                p.negative_prompt = f"{p.negative_prompt},{additional_neg_text}".strip(',')

        if isinstance(p.negative_prompt, list) and len(p.negative_prompt) > 1:
            try:
                neg_prompt_tokens = [model_hijack.get_prompt_lengths(pr_neg)[1] for pr_neg in p.negative_prompt]
                if len(set(neg_prompt_tokens)) != 1:
                    print('[Ranbooru] Padding negative prompts to consistent token length.')
                    max_tokens = max(neg_prompt_tokens)
                    for num_neg_pad, neg_len_item in enumerate(neg_prompt_tokens):
                        current_neg_item_parts = [part for part in p.negative_prompt[num_neg_pad].split(',') if part.strip()]
                        while model_hijack.get_prompt_lengths(p.negative_prompt[num_neg_pad])[1] < max_tokens:
                            choice_for_padding = random.choice(current_neg_item_parts) if current_neg_item_parts else "_"
                            p.negative_prompt[num_neg_pad] = f"{p.negative_prompt[num_neg_pad]},{choice_for_padding}"
            except Exception as e:
                print(f"[Ranbooru] Warning: Could not perform negative prompt padding: {e}")

        # limit_tags from UI is limit_tags_percentage
        # max_tags_slider from UI is max_tags_count
        if limit_tags < 1.0:
            if isinstance(p.prompt, list):
                p.prompt = [limit_prompt_tags(pr_limit, limit_tags, 'Limit') for pr_limit in p.prompt]
            else:
                p.prompt = limit_prompt_tags(p.prompt, limit_tags, 'Limit')

        if max_tags_slider > 0:
            if isinstance(p.prompt, list):
                p.prompt = [limit_prompt_tags(pr_max, max_tags_slider, 'Max') for pr_max in p.prompt]
            else:
                p.prompt = limit_prompt_tags(p.prompt, max_tags_slider, 'Max')

        if isinstance(p.prompt, list):
            p.prompt = [remove_repeated_tags(pr_rep) for pr_rep in p.prompt]
        else:
            p.prompt = remove_repeated_tags(p.prompt)

        if use_same_seed:
            p.seed = random.randint(0, 2**32 - 1) if p.seed == -1 else p.seed
            p.subseed = random.randint(0, 2**32-1) if p.subseed == -1 else p.subseed
            if hasattr(p, 'batch_size') and p.batch_size is not None and hasattr(p, 'n_iter') and p.n_iter is not None:
                 total_images = p.batch_size * p.n_iter
                 p.all_seeds = [p.seed] * total_images
                 p.all_subseeds = [p.subseed] * total_images


        p = self.loranado(lora_enabled_ui, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev)

        if use_deepbooru and not use_img2img:
            if self.last_img:
                print("[Ranbooru] Applying DeepBooru (txt2img mode)...")
                deepbooru_generated_tags_list = self.use_autotagger('deepbooru')

                if isinstance(p.prompt, list):
                    if len(deepbooru_generated_tags_list) < len(p.prompt):
                        last_tag_val = deepbooru_generated_tags_list[-1] if deepbooru_generated_tags_list else ""
                        deepbooru_generated_tags_list.extend([last_tag_val] * (len(p.prompt) - len(deepbooru_generated_tags_list)))
                    elif len(deepbooru_generated_tags_list) > len(p.prompt):
                         deepbooru_generated_tags_list = deepbooru_generated_tags_list[:len(p.prompt)]

                    p.prompt = [modify_prompt(p.prompt[i], deepbooru_generated_tags_list[i], type_deepbooru) for i in range(len(p.prompt))]
                    p.prompt = [remove_repeated_tags(pr_deep) for pr_deep in p.prompt]
                else:
                    current_db_tags = deepbooru_generated_tags_list[0] if deepbooru_generated_tags_list else ""
                    p.prompt = modify_prompt(p.prompt, current_db_tags, type_deepbooru)
                    p.prompt = remove_repeated_tags(p.prompt)
            else:
                print("[Ranbooru] DeepBooru (txt2img) selected, but no source images were fetched/available.")

        if use_img2img and use_ip:
            if self.last_img:
                print("[Ranbooru] Setting up ControlNet for img2img...")
                try:
                    controlNetModule = importlib.import_module('extensions.sd-webui-controlnet.scripts.external_code', 'external_code')
                    controlNetList = controlNetModule.get_all_units_in_processing(p)
                    if controlNetList:
                        cn_unit_to_modify = controlNetList[0]
                        copied_network_params = cn_unit_to_modify.__dict__.copy()
                        copied_network_params['enabled'] = True
                        copied_network_params['weight'] = denoising
                        img_for_cn = self.last_img[0]
                        if not isinstance(img_for_cn, np.ndarray):
                             img_for_cn = np.array(img_for_cn.convert("RGB"))

                        copied_network_params['image'] = {'image': img_for_cn, 'mask': None}

                        updated_cn_units = [controlNetModule.ControlNetUnit(**copied_network_params)] + controlNetList[1:]
                        controlNetModule.update_cn_script_in_processing(p, updated_cn_units)
                        print("[Ranbooru] ControlNet parameters updated with fetched image.")
                    else:
                        print("[Ranbooru] ControlNet (use_ip) enabled, but no ControlNet units found in processing details.")
                except ImportError:
                    print("[Ranbooru] Warning: ControlNet extension not found, cannot use 'Send to ControlNet' (use_ip).")
                except Exception as e_cn:
                    print(f"[Ranbooru] Error setting up ControlNet: {e_cn}")
            else:
                print("[Ranbooru] ControlNet (use_ip) selected, but no source images were fetched/available.")

        if use_img2img and not use_ip:
            p.steps = 1
            print(f"[Ranbooru] Img2Img (direct) mode: steps set to 1. Full processing in postprocess with {self.real_steps} steps.")

        if isinstance(p.prompt, list) and len(p.prompt) == 1:
            p.prompt = p.prompt[0]
        if isinstance(p.negative_prompt, list) and len(p.negative_prompt) == 1:
            p.negative_prompt = p.negative_prompt[0]

        print(f"[Ranbooru] Final positive prompt(s): {str(p.prompt)[:300]}{'...' if len(str(p.prompt)) > 300 else ''}")
        print(f"[Ranbooru] Final negative prompt(s): {str(p.negative_prompt)[:300]}{'...' if len(str(p.negative_prompt)) > 300 else ''}")

    def postprocess(self, p, processed, *args):
        if self.use_img2img_flag and not self.use_ip_flag and self.enabled_flag:
            if not self.last_img:
                print("[Ranbooru] Postprocess: Img2Img selected but no images available in self.last_img. Skipping.")
                return

            print(f"[Ranbooru] Postprocess: Starting Img2Img processing for {len(self.last_img)} image(s).")

            target_width = p.width
            target_height = p.height

            processed_init_images = []
            if self.crop_center_flag:
                print(f"[Ranbooru] Cropping/resizing images to {target_width}x{target_height} (center crop).")
                for img_item_crop in self.last_img:
                    processed_init_images.append(resize_image(img_item_crop, target_width, target_height, cropping=True))
            else:
                print(f"[Ranbooru] Resizing images to {target_width}x{target_height} (no cropping).")
                temp_resized_imgs = []
                for img_item_resize in self.last_img:
                     temp_resized_imgs.append(resize_image(img_item_resize, target_width, target_height, cropping=False))
                processed_init_images = temp_resized_imgs

            self.last_img = processed_init_images

            final_prompts_for_sdp = p.prompt
            final_negative_prompts_for_sdp = p.negative_prompt

            if self.use_deepbooru_flag:
                print("[Ranbooru] Applying DeepBooru (img2img mode)...")
                deepbooru_generated_tags_list = self.use_autotagger('deepbooru')

                if isinstance(final_prompts_for_sdp, list):
                    if len(deepbooru_generated_tags_list) < len(final_prompts_for_sdp):
                        last_tag_val = deepbooru_generated_tags_list[-1] if deepbooru_generated_tags_list else ""
                        deepbooru_generated_tags_list.extend([last_tag_val] * (len(final_prompts_for_sdp) - len(deepbooru_generated_tags_list)))
                    elif len(deepbooru_generated_tags_list) > len(final_prompts_for_sdp):
                         deepbooru_generated_tags_list = deepbooru_generated_tags_list[:len(final_prompts_for_sdp)]

                    final_prompts_for_sdp = [modify_prompt(final_prompts_for_sdp[i], deepbooru_generated_tags_list[i], self.type_deepbooru_val) for i in range(len(final_prompts_for_sdp))]
                    final_prompts_for_sdp = [remove_repeated_tags(pr_deep_img2img) for pr_deep_img2img in final_prompts_for_sdp]
                else:
                    current_db_tags_img2img = deepbooru_generated_tags_list[0] if deepbooru_generated_tags_list else ""
                    final_prompts_for_sdp = modify_prompt(final_prompts_for_sdp, current_db_tags_img2img, self.type_deepbooru_val)
                    final_prompts_for_sdp = remove_repeated_tags(final_prompts_for_sdp)

            num_prompts = len(final_prompts_for_sdp) if isinstance(final_prompts_for_sdp, list) else 1
            if len(self.last_img) != num_prompts:
                if not self.last_img:
                     print("[Ranbooru] Error: No init images for img2img postprocessing.")
                     return
                print(f"[Ranbooru] Warning: Mismatch between number of prompts ({num_prompts}) and init images ({len(self.last_img)}). Adjusting images.")
                if num_prompts > len(self.last_img):
                    self.last_img.extend([self.last_img[-1]] * (num_prompts - len(self.last_img)))
                else:
                    self.last_img = self.last_img[:num_prompts]


            sdp = StableDiffusionProcessingImg2Img(
                sd_model=shared.sd_model,
                outpath_samples=shared.opts.outdir_samples or shared.opts.outdir_img2img_samples,
                outpath_grids=shared.opts.outdir_grids or shared.opts.outdir_img2img_grids,
                prompt=final_prompts_for_sdp,
                negative_prompt=final_negative_prompts_for_sdp,
                seed=p.seed,
                subseed=p.subseed if hasattr(p, 'subseed') else -1,
                all_seeds=p.all_seeds if hasattr(p,'all_seeds') else None,
                all_subseeds=p.all_subseeds if hasattr(p,'all_subseeds') else None,
                sampler_name=p.sampler_name,
                scheduler=p.scheduler if hasattr(p, 'scheduler') else None,
                batch_size=p.batch_size,
                n_iter=p.n_iter,
                steps=self.real_steps,
                cfg_scale=p.cfg_scale,
                width=target_width,
                height=target_height,
                init_images=self.last_img,
                denoising_strength=self.denoising_strength,
                styles=p.styles if hasattr(p, 'styles') else None,
                override_settings=p.override_settings if hasattr(p,'override_settings') else None,
            )

            if isinstance(final_prompts_for_sdp, list):
                 sdp.n_iter = 1
                 sdp.batch_size = len(final_prompts_for_sdp)
                 if sdp.all_seeds and len(sdp.all_seeds) != len(final_prompts_for_sdp): # type: ignore
                     sdp.all_seeds = [sdp.seed] * len(final_prompts_for_sdp)
                 if sdp.all_subseeds and len(sdp.all_subseeds) != len(final_prompts_for_sdp): # type: ignore
                     sdp.all_subseeds = [sdp.subseed if hasattr(sdp,'subseed') else -1] * len(final_prompts_for_sdp)


            print("[Ranbooru] Invoking process_images for img2img...")
            processed_output = process_images(sdp)

            processed.images = processed_output.images
            processed.infotexts = processed_output.infotexts
            processed.prompt = final_prompts_for_sdp
            processed.negative_prompt = final_negative_prompts_for_sdp

            if self.use_last_img_flag and self.last_img:
                processed.images.append(self.last_img[0])
                processed.infotexts.append(f"Source image for img2img (use_last_img=True). Prompt: {p.prompt[0] if isinstance(p.prompt,list) else p.prompt}")
            elif not self.use_last_img_flag and self.last_img:
                 print(f"[Ranbooru] Appending {len(self.last_img)} source image(s) to results.")
                 for src_idx, src_img_item in enumerate(self.last_img):
                      processed.images.append(src_img_item)
                      src_prompt_info = ""
                      if isinstance(p.prompt, list) and src_idx < len(p.prompt): src_prompt_info = p.prompt[src_idx]
                      elif isinstance(p.prompt, str): src_prompt_info = p.prompt
                      processed.infotexts.append(f"Source image {src_idx+1} for img2img. Prompt context: {str(src_prompt_info)[:100]}")

            print("[Ranbooru] Img2Img postprocessing complete.")
        elif not self.enabled_flag:
             pass
        else:
             print("[Ranbooru] Postprocess: Not an img2img run (or use_ip=True), or script disabled. No Ranbooru postprocessing actions.")
