import os
import sqlite3
import time

import cairosvg
import moviepy.editor as mp
import nltk
import requests
import wikipedia
from PIL import Image
from gtts import gTTS
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from pytrends.request import TrendReq
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def generate_chrome_options():
    username = os.getlogin()
    # Configure Chrome options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')  # Run Chrome in headless mode (without a visible browser window)
    chrome_options.add_argument('--no-sandbox')  # Bypass OS security model
    chrome_options.add_argument('--disable-dev-shm-usage')  # Disable "DevShmUsage" flag
    chrome_options.add_argument(fr'--user-data-dir=C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data')
    chrome_options.add_argument(
        fr'--profile-directory=C:\\Users\\{username}\\AppData\\Local\\Google\\Chrome\\User Data\\Default')
    return chrome_options


def create_workspace():
    workspace_path = os.path.join(os.getcwd(), "workspace", query)
    images_dir = os.path.join(workspace_path, "images")
    synced_images_dir = os.path.join(workspace_path, "synced")
    audio_dir = os.path.join(workspace_path, "audio")
    video_dir = os.path.join(workspace_path, "video", query)
    audio_path = os.path.join(audio_dir, "speak.mp3")
    video_path = os.path.join(video_dir, f"{query}.mp4")
    os.makedirs(workspace_path, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(synced_images_dir, exist_ok=True)
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    return workspace_path, audio_path, video_path, audio_dir, video_dir, synced_images_dir, images_dir


def get_wikipedia_summary():
    try:
        data = wikipedia.page(title=query, auto_suggest=True)
        text = data.summary
        images = data.images
        title = data.title
        return title, text, images
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options
        data = wikipedia.page(title=options[1], auto_suggest=True)
        text = data.summary
        images = data.images
        title = data.title
        return title, text, images
    except wikipedia.exceptions.PageError as e:
        print(f"Error: {e}")


def download_images():
    supported_formats = ['svg', 'jpeg', 'png', 'bmp', 'gif', 'ppm', 'blp', 'bufr', 'cur', 'pcx', 'dcx', 'dds', 'eps',
                         'fits', 'fli', 'ftex', 'gbr', 'grib', 'hdf5', 'jpeg2000', 'icns', 'ico', 'im', 'imt', 'iptc',
                         'mcidas', 'mpeg', 'tiff', 'msp', 'pcd', 'pixar', 'psd', 'qoi', 'sgi', 'spider', 'sun', 'tga',
                         'webp', 'wmf', 'xbm', 'xpm', 'xvthumb']

    for i, i_url in enumerate(images_list):
        response = requests.get(i_url)
        if response.status_code == 200:
            image_path = os.path.join(images_dir, f"image_{i}")
            content_type = response.headers['Content-Type']
            image_extension = None

            for format in supported_formats:
                if format in content_type:
                    image_extension = format
                    break

            if image_extension is None:
                print(f"Unsupported image format for image {i + 1}/{i}. Skipping.")
                continue

            image_path += f".{image_extension}"

            # If the image format is SVG, convert it to PNG using cairosvg
            if image_extension == 'svg':
                svg_content = response.content
                png_content = cairosvg.svg2png(bytestring=svg_content)
                with open(image_path.replace(".svg", ".png"), 'wb') as f:
                    f.write(png_content)
            else:
                with open(image_path, "wb") as f:
                    f.write(response.content)
            print(f"Image {i + 1}/{i} downloaded successfully.")
        else:
            print(f"Failed to download image {i + 1}/{i}. Status code: {response.status_code}")


def sync_images():
    downloaded_images_list = []

    for downloaded_image_name in os.listdir(images_dir):
        downloaded_images_list.append(os.path.join(images_dir, downloaded_image_name))

    # Find the smallest photo in the list
    smallest_size = None
    for file_path in downloaded_images_list:
        image = Image.open(file_path)
        if smallest_size is None or image.size[0] < smallest_size[0]:
            smallest_size = image.size

    for file_path in downloaded_images_list:
        # Open the image file
        image = Image.open(file_path)

        # Convert the image to RGB if not already in RGB format
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize the image to a 9:16 aspect ratio
        aspect_ratio = 9 / 16
        new_width = int(smallest_size[1] * aspect_ratio)
        image = image.resize((new_width, smallest_size[1]), resample=Image.LANCZOS)
        # Save the image to the synced folder as JPEG
        filename = os.path.basename(file_path)
        image.save(os.path.join(synced_images_dir, filename), "JPEG")
        os.remove(file_path)


def create_video():
    # Load images and calculate duration of each image
    images = os.listdir(synced_images_dir)
    per_image_duration = duration / len(images)
    clips = []
    # Create a video
    for i, image in enumerate(images):
        clip = mp.ImageClip(img=os.path.join(synced_images_dir, image), duration=per_image_duration)
        clip.fps = 24
        clips.append(clip)

    video = mp.concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)

    # Save the video
    video.write_videofile(video_path, fps=24, codec="mpeg4")


def generate_keywords(text):
    # Tokenize the text into individual words
    tokens = word_tokenize(text)

    # Remove stopwords (common words that don't carry much meaning)
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word.lower() not in stop_words]

    # Perform part-of-speech tagging
    tagged_tokens = nltk.pos_tag(filtered_tokens)

    # Extract nouns and adjectives as keywords
    keywords = [word for word, pos in tagged_tokens if pos.startswith('N') or pos.startswith('J')]
    return keywords


def short_keywords(keyword_list):
    """
    This function takes a list of keywords and returns a shorter list of keywords,
    up to a maximum of 500 characters. The keywords are separated by commas.

    Args:
      keyword_list: A list of strings.

    Returns:
      A string of keywords, separated by commas.
    """
    # Generate a string from list with commas separating the keywords.
    keyword_string = ','.join(keyword_list)
    # Get the length of the keyword string.
    length = len(keyword_string)

    # If the keyword string is less than or equal to 500 characters, return it as a string.
    if length <= 500:
        return keyword_string
    else:
        new_list = []
        total_length = 0

        # Iterate through the keyword_list and add keywords to new_list until the total length exceeds 500 characters.
        for keyword in keyword_list:
            # Check if adding the current keyword exceeds the maximum length of 500 characters.
            if total_length + len(keyword) + len(new_list) <= 500:
                new_list.append(keyword)
                total_length += len(keyword)
            else:
                break

        # Return the new list of keywords as a string, separated by commas.
        return ','.join(new_list)


def upload_video_youtube(file_path, description: str, title: str, keywords: str):
    try:
        wait = WebDriverWait(driver, 10)

        create_icon = wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, '#create-icon > div')))
        create_icon.click()
        time.sleep(1)

        text_item = wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, '#text-item-0 yt-formatted-string')))
        text_item.click()
        time.sleep(1)

        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(file_path)
        time.sleep(1)

        # Wait for the details section to be visible
        wait.until(ec.visibility_of_element_located((By.ID, 'reuse-details-button')))
        time.sleep(1)

        # Fill in the video title
        title_input = driver.find_element(By.XPATH,
                                          '/html/body/ytcp-uploads-dialog/tp-yt-paper-dialog/div/ytcp-animatable[1]/ytcp-ve/ytcp-video-metadata-editor/div/ytcp-video-metadata-editor-basics/div[1]/ytcp-social-suggestions-textbox/ytcp-form-input-container/div[1]/div[2]/div/ytcp-social-suggestion-input/div')
        time.sleep(0.5)
        title_input.clear()
        time.sleep(0.5)
        title_input.send_keys(title)
        time.sleep(1)

        # Fill in the video description
        description_input = wait.until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, 'div.description ytcp-social-suggestion-input > div')))
        description_input.send_keys(description)
        time.sleep(1)

        # Set the video as not made for kids
        not_made_for_kids_radio = wait.until(ec.element_to_be_clickable(
            (By.CSS_SELECTOR, 'ytkc-made-for-kids-select tp-yt-paper-radio-button:nth-of-type(2) ytcp-ve')))
        not_made_for_kids_radio.click()
        time.sleep(1)

        # Enable comments on the video
        toggle_comments_button = wait.until(ec.element_to_be_clickable((By.CSS_SELECTOR, '#toggle-button > div')))
        toggle_comments_button.click()

        time.sleep(2)

        # Add tags to the video
        tags_input = wait.until(ec.visibility_of_element_located((By.XPATH,
                                                                  '/html/body/ytcp-uploads-dialog/tp-yt-paper-dialog/div/ytcp-animatable[1]/ytcp-ve/ytcp-video-metadata-editor/div/ytcp-video-metadata-editor-advanced/div[4]/ytcp-form-input-container/div[1]/div/ytcp-free-text-chip-bar/ytcp-chip-bar/div/input')))
        tags_input.send_keys(keywords)
        time.sleep(1)

        next_button = driver.find_element(By.XPATH, '//*[@id="next-button"]')
        for i in range(3):
            next_button.click()
            time.sleep(1)

        public_button = wait.until(ec.element_to_be_clickable((By.NAME, 'PUBLIC')))
        # Click the "Public" button
        public_button.click()
        time.sleep(1)

        done_button = wait.until(ec.element_to_be_clickable((By.ID, "done-button")))
        done_button.click()
        time.sleep(3)
        close_button = wait.until(ec.element_to_be_clickable((By.XPATH, '//ytcp-button[@id="close-button"]')))

        # Click the "Kapat" button
        close_button.click()
        time.sleep(3)
    except Exception as e:
        print(e)
        time.sleep(500)


if __name__ == "__main__":
    # Start ChromeDriver with options.
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=generate_chrome_options())
    driver.get("https://studio.youtube.com/")

    # Connect to the SQLite database
    conn = sqlite3.connect('processed_trends.db')
    cursor = conn.cursor()
    # Create a table to store processed trends if it doesn't exist
    cursor.execute('''CREATE TABLE IF NOT EXISTS trends (trend_name text)''')
    conn.commit()
    # Get Trends.
    trends = TrendReq().trending_searches(pn='united_states')

    for query in trends.iloc[:, 0]:
        # Check if the trend has already been processed
        cursor.execute("SELECT * FROM trends WHERE trend_name=?", (query,))
        result = cursor.fetchone()
        if result:
            print(f"{query} ")

        else:
            # Process the trend
            print(f"Beginning process for {query}.")
            workspace_path, audio_path, video_path, audio_dir, video_dir, synced_images_dir, images_dir = create_workspace()
            print(f"Getting Wikipedia Data")
            wiki_title, summary, images_list = get_wikipedia_summary()
            print(f"Wikipedia data scrapped.")
            print(f"{query} replaced: New page title: {wiki_title}")
            if summary:
                # Create audio
                language = "en"
                speech = gTTS(text=summary, lang=language, slow=False)
                os.makedirs(os.path.dirname(audio_path), exist_ok=True)
                speech.save(audio_path)
                audio = mp.AudioFileClip(audio_path)
                duration = int((round(audio.duration)) / 5)
                # End of audio process
                download_images()
                sync_images()
                create_video()
                shortened_tags_result = short_keywords(generate_keywords(summary))
                upload_video_youtube(file_path=video_path, description=summary, title=wiki_title,
                                     keywords=shortened_tags_result)

                # Store the processed trend in the database
                cursor.execute("INSERT INTO trends VALUES (?)", (query,))
                conn.commit()

    # Close the database connection
    conn.close()
    exit()
