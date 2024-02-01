import re
import threading
import time
# from weasyprint import HTML
import requests
import pdfkit
from bs4 import BeautifulSoup, Tag
import os
from PyPDF2 import PdfReader, PdfWriter
import imgkit
from fpdf import FPDF
from PIL import Image


def merge_pdfs(paths, output):
    try:
        pdf_writer = PdfWriter()
        for path in sorted(paths, key=lambda x: int(re.search(r'(\d+)', os.path.basename(x)).group())):
            pdf_reader = PdfReader(path)
            for page in range(len(pdf_reader.pages)):
                pdf_writer.add_page(pdf_reader.pages[page])
        with open(output, 'wb') as out:
            pdf_writer.write(out)
    except Exception as e:
        print(f"合并 PDF 文件时发生错误: {e}")
        # 或者进行其他异常处理


def merge_pdfs_in_batches(paths, output, batch_size=50):
    intermediate_files = []
    for i in range(0, len(paths), batch_size):
        batch_paths = paths[i:i + batch_size]
        intermediate_file = f"{output}_part_{i // batch_size}.pdf"
        merge_pdfs(batch_paths, intermediate_file)
        intermediate_files.append(intermediate_file)

    merge_pdfs(intermediate_files, output)

    # 删除中间文件
    for file in intermediate_files:
        os.remove(file)


def find_pdfs(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.pdf'):
                yield os.path.join(root, file)


def fetch_html(url, headers):
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"网络请求错误: {e}")
        # 或者根据您的需求进行其他处理


def convert_html_to_pdf(html, output_pdf, stop_event, output_jpg=''):
    options = {
        'page-size': 'Letter',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': 'UTF-8',
        'no-outline': None,
        'disable-smart-shrinking': '',
    }
    try:
        clean_html_content = clean_html(html)
        if output_jpg:
            imgkit.from_string(clean_html_content, output_jpg)
            # 将图片转换为 PDF
            image = Image.open(output_jpg)
            image.save(output_pdf, save_all=True)
            print(f"成功将图片转换为 PDF: {output_pdf}")
        else:
            pdfkit.from_string(clean_html_content, output_pdf, options=options)
            print(f"成功将 HTML 转换为 PDF: {output_pdf}")
        if stop_event.is_set():
            print(f"线程接收到停止信号，终止处理: {output_pdf}")
            return
    except OSError as e:
        print(f"转换 HTML 到 PDF 时发生错误: {e}")
        if output_jpg:
            # 将图片转换为 PDF
            image = Image.open(output_jpg)
            image.save(output_pdf, save_all=True)
            print(f"成功将图片转换为 PDF: {output_pdf}")
        # 或者进行其他异常处理
    except Exception as e:
        print(f"发生其他异常: {e}")
        # 或者进行其他异常处理


def convert_html_to_pdf_in_thread(input_html_file, output_pdf_file, output_image):
    stop_event = threading.Event()
    thread = threading.Thread(target=convert_html_to_pdf, args=(input_html_file, output_pdf_file, stop_event, output_image))
    thread.start()
    return thread


def clean_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    body = soup.find('body')
    if body:
        button = body.find('button')
        if button:
            # 获取第一个 button 标签之后的所有元素
            next_elements = button.find_all_next()
            # 删除这些元素
            for element in next_elements:
                if isinstance(element, Tag):
                    element.decompose()
            # 最后删除 button 自身
            button.decompose()

    return str(soup)


def monitor_thread(thread, stop_event, timeout=300):
    """ 监控线程，如果超时，则设置停止事件 """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not thread.is_alive():
            # 如果原线程已经完成，立即退出监控器线程
            return
        time.sleep(1)  # 每秒检查一次

    if thread.is_alive():
        print(f"线程处理超时，准备停止线程: {thread.name}")
        stop_event.set()


def main(ebook_id, number, headers):
    threads = []  # 用于存储线程的列表
    for num in range(1, number + 1):
        output_pdf = f"{ebook_id}/{num}.pdf"
        output_jpg = f"{ebook_id}/{num}.jpg"
        url = f"https://book.qq.com/book-read/{ebook_id}/{num}"
        try:
            html = fetch_html(url, headers)
            time.sleep(1)
            # thread = convert_html_to_pdf_in_thread(html, output_file)
            # threads.append(thread)
            stop_event = threading.Event()
            thread = threading.Thread(target=convert_html_to_pdf, args=(html, output_pdf, stop_event, output_jpg))
            thread.start()
            monitor = threading.Thread(target=monitor_thread, args=(thread, stop_event))
            monitor.start()
            threads.append((thread, monitor))
            print("PDF successfully created as", output_pdf)
        except Exception as e:
            print("An error occurred:", e)

    # 等待所有线程和监控器完成
    for thread, monitor in threads:
        thread.join()
        monitor.join()


def extract_number(text):
    match = re.search(r'目录\((\d+)章\)', text)
    if match:
        return int(match.group(1))
    else:
        return None


def get_book_content(ebook_id, book_name):
    url = f'https://book.qq.com/book-chapter/{ebook_id}'
    # url = f"https://book.qq.com/book-read/32436084/51"
    # response = requests.get(url, headers=headers)
    # response.raise_for_status()
    output_pdf = f"{ebook_id}/0.pdf"
    output_jpg = f"{ebook_id}/0.jpg"
    html = fetch_html(url, headers)
    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(html, 'html.parser')
    # 定位到 class 为 'book-title-wrap' 的 <div> 标签
    book_title = soup.find('div', class_='book-title-wrap').get_text(strip=True)
    book_chapter_num = soup.find('div', class_='ypc-column-name tab-title').get_text(strip=True)
    book_name[ebook_id] = book_title
    # if book_title_div:
    #     book_title = book_title_div.get_text(strip=True)
    #     print("书名:", book_title)
    # else:
    #     print("未找到书名")
    number = extract_number(book_chapter_num)
    return book_name, number, html, output_pdf, output_jpg


if __name__ == "__main__":
    # 1.32
    # 1.32
    headers = {
        "Cookie": "ywguid=123456789; ywkey=123456789;",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    # book_list = [32436084, 32856983, 48162894, 47184389, 34916570, 47755419, 26297912, 25916013, 24027607]
    # book_list = [33211566, 622012]
    book_list = [36090231, 654450]
    book_name = {}
    for ebook_id in book_list:
        number = 0
        try:
            os.mkdir(f'{ebook_id}')
            book_name, number, html, output_pdf, output_jpg = get_book_content(ebook_id, book_name)
            print(book_name)
            # print(number)
            # with open(f"{ebook_id}/1.html", 'w', encoding='utf-8') as file:
            #     file.write(html)
            convert_html_to_pdf_in_thread(html, output_pdf, output_jpg)
        except Exception:
            pass

        main(ebook_id, number, headers)
    #
    # # clean_html('temp.html')
    #
    for ebook_id in book_list:
        # book_dir = str(ebook_id)  # 假设目录名就是书籍编号
        # pdf_files = list(find_pdfs(book_name[ebook_id])
        print('开始合书')
        # print(book_name)
        book_dir = book_name[ebook_id]
        pdf_files = list(find_pdfs(str(ebook_id)))
        if pdf_files:
            merge_pdfs_in_batches(pdf_files, f'{book_dir}.pdf')
            print(f"Merged PDFs for book {ebook_id} into {book_dir}.pdf")
        else:
            print(f"No PDFs found for book {ebook_id}")
