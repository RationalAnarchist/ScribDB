from ebooklib import epub
import ebooklib
import tempfile
import os

path = "debug.epub"
book = epub.EpubBook()
book.set_identifier('id123456')
book.set_title('Sample Book')
book.add_author('Author Name')

c1 = epub.EpubHtml(title='Intro', file_name='intro.xhtml', lang='en')
c1.content = '<h1>Intro</h1><p>Epub Content.</p>'
book.add_item(c1)

# Correct spine usage
book.spine = [c1]

epub.write_epub(path, book, {})

# Read back
try:
    read_book = epub.read_epub(path)
    print(f"Spine: {read_book.spine}")
    for item_tuple in read_book.spine:
        print(f"Item tuple: {item_tuple}")
        # Typically (item_id, linear)
        item_id = item_tuple[0]
        item = read_book.get_item_with_id(item_id)
        print(f"Item: {item}")
        if item:
            print(f"Type: {item.get_type()}")
            print(f"Content: {item.get_content()}")
finally:
    if os.path.exists(path):
        os.remove(path)
