import requests
import os
from bs4 import BeautifulSoup
from pathvalidate import sanitize_filename
from urllib.parse import urljoin
import json
import re
import logging
import argparse


def download_txt(url, filename, folder='books/'):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()
    if response.status_code == 200:
        filename = sanitize_filename(f'{filename}.txt')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        with open(path, 'wb') as file:
            file.write(response.content)

        return path


def get_book_image_url(soup):
    img_link = soup.select_one('.bookimage a img')['src']

    return urljoin('http://tululu.org', img_link)


def download_image(url, folder='images/'):

    os.makedirs(folder, exist_ok=True)

    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()
    filename = sanitize_filename(f'{url.split("/")[-1]}')

    path = os.path.join(folder, filename)
    with open(path, 'wb') as file:
        file.write(response.content)

    return path


def get_book_comments(soup):
    comments = [comment.select_one('span.black').text for comment in soup.select('div.texts')]

    return comments


def get_genre(soup):
    genres = [genre.text for genre in soup.select('span.d_book a')]

    return genres


def get_book_title_and_author(soup):
    header = soup.select_one('h1').text
    title, author = header.split('::')

    return title.strip(), author.strip()


def get_all_book_data(soup, book_page_url, skip_txt, skip_images, dest_folder):
    book_data = {}
    title, author = get_book_title_and_author(soup)
    genres = get_genre(soup)
    book_data['title'] = title
    book_data['author'] = author

    if dest_folder:
        os.makedirs(dest_folder, exist_ok=True)

    if not skip_images:
        image_url = get_book_image_url(soup)
        images_folder = os.path.join(dest_folder, 'images')
        image_path = download_image(image_url, images_folder)
        book_data['img_src'] = image_path

    if not skip_txt:
        book_number = re.findall(r'\d+', book_page_url)[0]
        txt_download_link = f'http://tululu.org/txt.php?id={book_number}'
        books_folder = os.path.join(dest_folder, 'books')
        book_path = download_txt(txt_download_link, title, books_folder)
        book_data['book_path'] = book_path

    comments = get_book_comments(soup)
    book_data['comments'] = comments
    book_data['genres'] = genres

    return book_data


def get_book_links(url):
    links = []
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'lxml')
    book_cards = soup.select('table.d_book')
    for card in book_cards:
        book_relative_url = card.select_one('a')['href']
        links.append(urljoin('http://tululu.org', book_relative_url))

    return links


if __name__ == '__main__':

    books_data = []
    all_links = []

    parser = argparse.ArgumentParser(description='Парсер библиотеки tululu.org')
    parser.add_argument('--start_page', default=1, help='Номер страницы, с которой начать скачивание', type=int)
    parser.add_argument('--end_page', help='Номер страницы, на которой закончить скачивание', type=int)
    parser.add_argument('--filename', default='books.json', help='Имя json-файла, в который сохраняются данные')
    parser.add_argument('--skip_txt', default=False, help='Пропустить загрузку файлов книг', type=bool, required=False)
    parser.add_argument('--skip_images', default=False, help='Пропустить загрузку изображений книг', type=bool,
                        required=False)
    parser.add_argument('--dest_folder', default='', help='Директория для хранения файлов', type=str, required=False)

    args = parser.parse_args()

    json_books_file = os.path.join(args.dest_folder, args.filename)

    if args.end_page > args.start_page > 0:
        for num in range(args.start_page, args.end_page):
            try:
                url = 'http://tululu.org/l55/{}/'.format(num)
                all_links.extend(get_book_links(url))
            except requests.exceptions.HTTPError as e:
                logging.error('Невозможно загрузить страницу.', exc_info=True)
        else:
            for html_page_url in all_links:
                try:
                    response = requests.get(html_page_url)
                    response.raise_for_status()
                    if response.url == 'http://tululu.org/':
                        continue
                    soup = BeautifulSoup(response.text, 'lxml')
                    book_data = get_all_book_data(soup, html_page_url, args.skip_txt, args.skip_images, args.dest_folder)
                    books_data.append(book_data)
                except requests.exceptions.HTTPError as e:
                    logging.error('Невозможно загрузить страницу.')

        with open(json_books_file, 'w') as my_file:
            json.dump(books_data, my_file, ensure_ascii=False)

    else:
        logging.error('Указаны неверные номера страниц.')