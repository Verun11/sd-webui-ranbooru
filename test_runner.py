import os
import sys
import random
import types

# --- Source code of ranbooru.py (with process_wildcards) ---
# This content is taken from the successful application of replace_with_git_merge_diff
# in the earlier subtask (turn 16 / output of tool call in turn 15).
ranbooru_py_content = """
from io import BytesIO
import html
import random
import requests
import re # Added
import modules.scripts as scripts
import gradio as gr
import os
from PIL import Image
import numpy as np
import importlib
import requests_cache

from modules.processing import process_images, StableDiffusionProcessingImg2Img
from modules import shared
from modules.sd_hijack import model_hijack
from modules import deepbooru
from modules.ui_components import InputAccordion

extension_root = scripts.basedir()
user_data_dir = os.path.join(extension_root, 'user')
user_search_dir = os.path.join(user_data_dir, 'search')
user_remove_dir = os.path.join(user_data_dir, 'remove')
user_forbidden_prompt_dir = os.path.join(user_data_dir, 'forbidden_prompt')
user_wildcards_dir = os.path.join(user_data_dir, 'wildcards') # Added wildcard directory
os.makedirs(user_search_dir, exist_ok=True)
os.makedirs(user_remove_dir, exist_ok=True)
os.makedirs(user_forbidden_prompt_dir, exist_ok=True)
os.makedirs(user_wildcards_dir, exist_ok=True) # Ensure wildcard directory is created

if not os.path.isfile(os.path.join(user_search_dir, 'tags_search.txt')):
    with open(os.path.join(user_search_dir, 'tags_search.txt'), 'w'):
        pass
if not os.path.isfile(os.path.join(user_remove_dir, 'tags_remove.txt')):
    with open(os.path.join(user_remove_dir, 'tags_remove.txt'), 'w'):
        pass
if not os.path.isfile(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt')):
    with open(os.path.join(user_forbidden_prompt_dir, 'tags_forbidden.txt'), 'w') as f:
        f.write("# Add tags here, one per line\\n")
        f.write("artist_name_example\\n")
        f.write("character_name_example\\n")

COLORED_BG = ['black_background', 'aqua_background', 'white_background', 'colored_background', 'gray_background', 'blue_background', 'green_background', 'red_background', 'brown_background', 'purple_background', 'yellow_background', 'orange_background', 'pink_background', 'plain', 'transparent_background', 'simple_background', 'two-tone_background', 'grey_background']
ADD_BG = ['outdoors', 'indoors']
BW_BG = ['monochrome', 'greyscale', 'grayscale']
POST_AMOUNT = 100
COUNT = 100
DEBUG = False
RATING_TYPES = {
    "none": {"All": "All"},
    "full": {"All": "All", "Safe": "safe", "Questionable": "questionable", "Explicit": "explicit"},
    "single": {"All": "All", "Safe": "g", "Sensitive": "s", "Questionable": "q", "Explicit": "e"}
}
RATINGS = {
    "e621": RATING_TYPES['full'], "danbooru": RATING_TYPES['single'], "aibooru": RATING_TYPES['full'],
    "yande.re": RATING_TYPES['full'], "konachan": RATING_TYPES['full'], "safebooru": RATING_TYPES['none'],
    "rule34": RATING_TYPES['full'], "xbooru": RATING_TYPES['full'], "gelbooru": RATING_TYPES['single']
}

def get_available_ratings(booru): return gr.Radio.update(choices=RATINGS[booru].keys(), value="All")
def show_fringe_benefits(booru): return gr.Checkbox.update(visible=(booru == 'gelbooru'))

def check_exception(booru, parameters):
    post_id = parameters.get('post_id')
    tags = parameters.get('tags')
    if booru == 'konachan' and post_id: raise Exception("Konachan does not support post IDs")
    if booru == 'yande.re' and post_id: raise Exception("Yande.re does not support post IDs")
    if booru == 'e621' and post_id: raise Exception("e621 does not support post IDs")
    if booru == 'danbooru' and tags and len(tags.split(',')) > 1: raise Exception("Danbooru does not support multiple tags. You can have only one tag.")

class Booru():
    def __init__(self, booru, booru_url):
        self.booru = booru
        self.booru_url = booru_url
        self.headers = {'user-agent': 'my-app/0.0.1'}
    def get_data(self, add_tags, max_pages=10, id=''): pass
    def get_post(self, add_tags, max_pages=10, id=''): pass

# ... (rest of Booru subclasses like Gelbooru, XBooru, etc. would go here, shortened for brevity in this plan) ...
# For the purpose of testing process_wildcards, these are not strictly needed if Script class can be instantiated.
# However, the original script has them, so for full exec, they should be included.
# Let's assume they are part of the ranbooru_py_content string.
class Gelbooru(Booru):
    def __init__(self, fringe_benefits): super().__init__('gelbooru', f'https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}'); self.fringeBenefits = fringe_benefits
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; return {'post': [], '@attributes': {'count': 0}} # Simplified
class XBooru(Booru):
    def __init__(self): super().__init__('xbooru', f'https://xbooru.com/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'post': []} # Simplified
class Rule34(Booru):
    def __init__(self): super().__init__('rule34', f'https://api.rule34.xxx/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'post': []} # Simplified
class Safebooru(Booru):
    def __init__(self): super().__init__('safebooru', f'https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'post': []} # Simplified
class Konachan(Booru):
    def __init__(self): super().__init__('konachan', f'https://konachan.com/post.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'post': []} # Simplified
class Yandere(Booru):
    def __init__(self): super().__init__('yande.re', f'https://yande.re/post.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'post': []} # Simplified
class AIBooru(Booru):
    def __init__(self): super().__init__('AIBooru', f'https://aibooru.online/posts.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'post': []} # Simplified
class Danbooru(Booru):
    def __init__(self): super().__init__('danbooru', f'https://danbooru.donmai.us/posts.json?limit={POST_AMOUNT}')
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'post': []} # Simplified
    def get_post(self, add_tags, max_pages=10, id=''): return {'post': [{'tag_string': 'test_tag'}]} # Simplified
class e621(Booru):
    def __init__(self): super().__init__('e621', f'https://e621.net/posts.json?limit={POST_AMOUNT}') # Corrected class name
    def get_data(self, add_tags, max_pages=10, id=''): global COUNT; COUNT = 0; return {'posts': []} # Simplified for e621 structure

def generate_chaos(pos_tags, neg_tags, chaos_amount): return pos_tags, neg_tags # Simplified
def resize_image(img, width, height, cropping=True): return img # Simplified
def modify_prompt(prompt, tagged_prompt, type_deepbooru): return prompt # Simplified
def remove_repeated_tags(prompt): return prompt # Simplified
def limit_prompt_tags(prompt, limit_tags, mode): return prompt # Simplified


class Script(scripts.Script): # This is ranbooru.Script, inheriting from modules.scripts.Script
    previous_loras = ''
    last_img = []
    real_steps = 0
    version = "1.2"
    original_prompt = ''

    def process_wildcards(self, current_tags_string):
        # Ensure re is available (already imported at the top of the script)
        processed_tags = current_tags_string
        wildcard_matches = re.findall(r'__([a-zA-Z0-9_]+)__', processed_tags)
        if not wildcard_matches:
            return current_tags_string

        # This refers to the global user_wildcards_dir defined at the top of this string
        # That user_wildcards_dir will be calculated using the mocked scripts.basedir()
        # global user_wildcards_dir # Make it explicit we are using the module's global

        for keyword in wildcard_matches:
            wildcard_pattern = f'__{keyword}__'
            replacement_tag = ""
            file_path = os.path.join(user_wildcards_dir, f"{keyword}.txt") # Uses module global
            if os.path.exists(file_path) and os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        possible_tags = [line.strip() for line in f if line.strip()]
                    if possible_tags:
                        replacement_tag = random.choice(possible_tags)
                except Exception as e:
                    print(f"[Ranbooru] Error reading wildcard file {file_path}: {e}")
            processed_tags = processed_tags.replace(wildcard_pattern, replacement_tag, 1)
        final_tags_list = [tag.strip() for tag in processed_tags.split(',') if tag.strip()]
        return ','.join(final_tags_list)

    def get_files(self, path): return [] # Mocked
    def hide_object(self, obj, booru): pass # Mocked
    def title(self): return "Ranbooru"
    def show(self, is_img2img): return scripts.AlwaysVisible # Mocked
    def refresh_ser(self): return gr.update(choices=[]) # Mocked
    def refresh_rem(self): return gr.update(choices=[]) # Mocked
    def get_forbidden_files(self): return ['tags_forbidden.txt'] # Mocked
    def refresh_forbidden_files(self): return gr.update(choices=[]) # Mocked
    def ui(self, is_img2img): # Mocked - simplified return
        # Need to return a list of Gradio components as per original structure
        # For testing process_wildcards, this complexity isn't strictly needed
        # as long as the class can be instantiated.
        # It calls self.elem_id, so the base Script mock needs that.
        print(f"Dummy Ranbooru Script UI method called. Elem_id base: {self.elem_id('ra_enable')}")
        return [gr.Checkbox(label="Dummy Checkbox")]


    def check_orientation(self, img): return [512,512] # Mocked
    def loranado(self, lora_enabled, lora_folder, lora_amount, lora_min, lora_max, lora_custom_weights, p, lora_lock_prev): return p # Mocked

    def before_process(self, p, enabled, tags, booru, remove_bad_tags, max_pages, change_dash, same_prompt, fringe_benefits, remove_tags, use_img2img, denoising, use_last_img, change_background, change_color, shuffle_tags, post_id, mix_prompt, mix_amount, chaos_mode, negative_mode, chaos_amount, limit_tags, max_tags, sorting_order, mature_rating, lora_folder, lora_amount, lora_min, lora_max, lora_enabled, lora_custom_weights, lora_lock_prev, use_ip, use_search_txt, use_remove_txt, choose_search_txt, choose_remove_txt, search_refresh_btn, remove_refresh_btn, forbidden_prompt_tags_text, use_forbidden_prompt_txt, choose_forbidden_prompt_txt, crop_center, use_deepbooru, type_deepbooru, use_same_seed, use_cache, disable_prompt_modification):
        self.original_prompt = p.prompt if hasattr(p, 'prompt') else ""
        tags = self.process_wildcards(tags) # This is what we want to test
        # Rest of before_process can be simplified or passivated for this test
        if hasattr(p, 'prompt'):
            p.prompt = tags # Simplified: assume p.prompt just becomes the processed tags
        return # Mocked

    def postprocess(self, p, processed, *args): pass # Mocked
    def random_number(self, sorting_order, size): return random.sample(range(100), size) # Mocked
    def use_autotagger(self, model): return ["autotagged_prompt"] # Mocked
"""

# --- Mocking necessary parts of the Stable Diffusion Web UI environment ---
if not os.path.exists("modules"): os.makedirs("modules")
with open("modules/scripts.py", "w") as f: f.write("import os\ndef basedir(): return os.path.abspath('.')\nclass Script:\n    def title(self): return 'BaseDummyScript'\n    def show(self, is_img2img): return True\n    def ui(self, is_img2img): return []\n    def elem_id(self, name): return name\n")
with open("modules/processing.py", "w") as f: f.write("def process_images(*args, **kwargs): return None\nclass StableDiffusionProcessingImg2Img: pass\n")
with open("modules/shared.py", "w") as f: f.write("class opts: pass\nsd_model = None\ncmd_opts = type('CmdOpts', (), {'deepbooru_score_threshold': 0.5})()\nstate = type('State', (), {'interrupted': False})()\n")
with open("modules/sd_hijack.py", "w") as f: f.write("class model_hijack:\n    @staticmethod\n    def get_prompt_lengths(prompt_text):\n        length = len(prompt_text.split(','))\n        return (length, (length // 75 + 1) * 75)\n")
with open("modules/deepbooru.py", "w") as f: f.write("class DeepDanbooru:\n    def start(self): pass\n    def stop(self): pass\n    def tag_multi(self, pil_image, threshold=0.5): return 'dummy_tag'\nmodel = DeepDanbooru()\n")
with open("modules/ui_components.py", "w") as f: f.write("import gradio as gr\nclass InputAccordion:\n    def __init__(self, open_by_default, label, elem_id=None): self.label = label\n    def __enter__(self): return self\n    def __exit__(self, exc_type, exc_val, exc_tb): pass\n")

sys.path.insert(0, os.path.abspath("."))

# --- Dynamically execute the embedded ranbooru.py content ---
ranbooru_module_globals = {}
# Populate with necessary pre-defined globals if any (e.g. 'scripts' if it's not re-imported in the string)
# The string content itself does `import modules.scripts as scripts` so mocks will be used.
# It also does `import os`, `import re`, `import random`.
exec(ranbooru_py_content, ranbooru_module_globals)
print("Executed embedded ranbooru.py content dynamically.")

RanbooruScriptClass = ranbooru_module_globals['Script']
# The global 'user_wildcards_dir' will be defined inside ranbooru_module_globals by the exec'd code.
# We must ensure it's correct for our test files.
# The exec'd code calculates it as: os.path.join(scripts.basedir(), 'user', 'wildcards')
# Our mocked scripts.basedir() returns ".", so it becomes "./user/wildcards" -> "/app/user/wildcards"
print(f"User wildcards dir from exec'd code: {ranbooru_module_globals.get('user_wildcards_dir')}")

script_instance = RanbooruScriptClass()

print(f"Attributes of dynamically loaded RanbooruScriptClass: {dir(RanbooruScriptClass)}")
if not hasattr(script_instance, 'process_wildcards'):
    print("CRITICAL Error: 'process_wildcards' STILL NOT FOUND.")
    sys.exit(1)
else:
    print("'process_wildcards' attribute FOUND.")

# --- Test Cases ---
test_inputs = {
    "T1": "__artist__", "T2": "__artist__, __series__", "T3": "1girl, __artist__, solo, __series__",
    "T4": "__nonexistent__", "T5": "__empty__", "T6": "__artist__, __nonexistent__, __series__",
    "T7": "before, __artist__, middle, __series__, after", "T8": "__artist__,__artist__",
    "T9": ",, __artist__ , , __series__ ,,"
}
results = {}
print("\nStarting wildcard processing tests...\n")
# Ensure the user_wildcards_dir used by process_wildcards is the one from the exec'd globals
# This is implicitly handled if process_wildcards correctly uses the global from its own module scope.

for test_name, tags_input in test_inputs.items():
    # Seed random for each call for slightly more predictable multiple choice from same file in T8
    # random.seed(sum(ord(c) for c in test_name)) # Basic seed based on test name
    output = script_instance.process_wildcards(tags_input)
    results[test_name] = output
    print(f"Input  ({test_name}): {tags_input}")
    print(f"Output ({test_name}): {output}\n")

print("\n--- Summary of Results ---")
for test_name, output in results.items():
    print(f"{test_name}: {output}")

print("\nTest execution finished.")

# Cleanup dummy modules directory
import shutil
if os.path.exists("modules"):
    try:
        shutil.rmtree("modules")
        print("Cleaned up dummy modules directory.")
    except Exception as e:
        print(f"Error cleaning up dummy modules: {e}")
