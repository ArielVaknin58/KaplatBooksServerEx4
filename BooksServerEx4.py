import time
from flask import Flask, request, jsonify, g
import logging
from datetime import datetime
import os

app = Flask(__name__)


class CustomFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            s = datetime.fromtimestamp(record.created).strftime(datefmt)
            return s + ".%03d" % record.msecs
        else:
            t = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            return t + ",%03d" % record.msecs


formatter = CustomFormatter('%(asctime)s %(levelname)s: %(message)s | request #%(request_num)d',
                            datefmt='%d-%m-%Y %H:%M:%S')

logs_folder_path = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(logs_folder_path):
    os.makedirs(logs_folder_path)


console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler_books = logging.FileHandler('logs/books.log', mode='a')
file_handler_books.setFormatter(formatter)

file_handler_requests = logging.FileHandler('logs/requests.log', mode='a')
file_handler_requests.setFormatter(formatter)

request_logger = logging.getLogger('request-logger')
request_logger.setLevel(logging.INFO)
request_logger.addHandler(console_handler)
request_logger.addHandler(file_handler_requests)

books_logger = logging.getLogger('books-logger')
books_logger.setLevel(logging.INFO)
books_logger.addHandler(console_handler)
books_logger.addHandler(file_handler_books)


class Book:

    def __init__(self, title, author, year, price, genres):
        self.title = title
        self.author = author
        self.year = year
        self.price = price
        self.genres = genres
        self.id = 0

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "price": self.price,
            "year": self.year,
            "genres": self.genres
        }


AvailableId = 1
request_num = 1
BooksList = list()


@app.before_request
def IncomingRequest():
    global request_num
    g.start_time = time.time()
    log_message_info = f"Incoming request | #{request_num} | resource: {request.path} | HTTP Verb {request.method.upper()}"
    request_logger.info(log_message_info, extra={'request_num': request_num})


@app.after_request
def AfterRequest(response):
    global request_num
    duration_ms = int((time.time() - g.start_time) * 1000)
    log_message_debug = f'request #{request_num} duration: {duration_ms}ms'
    request_logger.debug(log_message_debug, extra={'request_num': request_num})
    request_num += 1
    return response


@app.route('/books/health', methods=['GET'])
def Health():
    return "OK", 200


@app.route('/book', methods=['POST'])
def CreateBook():

    global AvailableId
    title = request.json.get('title')
    year = request.json.get('year')
    price = request.json.get('price')
    found = False
    if year < 1940 or year > 2100:
        answer = {
            'errorMessage': f"Error: Can't create new Book that its year {year} is not in the accepted range [1940 -> 2100]"}
        books_logger.error(answer['errorMessage'], extra={'request_num': request_num})
        return answer, 409
    if price <= 0:
        answer = {'errorMessage': "Error: Can't create new Book with negative price"}
        books_logger.error(answer['errorMessage'], extra={'request_num': request_num})
        return answer, 409
    for book in BooksList:
        book.title.lower()
        if book.title == title:
            answer = {'errorMessage': f'Error: Book with the title [{title}] already exists in the system'}
            books_logger.error(answer['errorMessage'], extra={'request_num': request_num})
            return answer, 409

    log_message_info = f"Creating new Book with Title [{title}]"
    books_logger.info(log_message_info, extra={'request_num': request_num})
    log_message_debug = f'Currently there are {len(BooksList)} Books in the system. New Book will be assigned with id {AvailableId}'
    books_logger.debug(log_message_debug, extra={'request_num': request_num})
    if not found:
        newBook = Book(title=title,
                       author=request.json.get('author').lower().title(),
                       year=year,
                       price=price,
                       genres=request.json.get('genres'))
        BooksList.append(newBook)
        newBook.id = AvailableId
        AvailableId += 1
        return jsonify({'result': newBook.id}), 200


@app.route('/books/total', methods=['GET'])
def total():
    args = request.args.to_dict()
    resBooks = FilterBooks(args, set(BooksList.copy()))
    genres = args.get('genres')
    if genres is not None:
        genres = genres.split(',')
        if not all(genre.isupper() for genre in genres):
            return jsonify({'error': 'Wrong case for genres'}), 400
    log_message_info = f'Total Books found for requested filters is {len(resBooks)}'
    books_logger.info(log_message_info, extra={'request_num': request_num})
    return jsonify({'result': len(resBooks)}), 200


def FilterBooks(args: dict, resBooks: set) -> set:
    RemovalSet = set()
    if args.get('author') is not None:
        for book in resBooks:
            if book.author != args.get('author').lower().title():
                RemovalSet.add(book)
    if args.get('price-bigger-than') is not None:
        for book in resBooks:
            if book.price < int(args.get('price-bigger-than')):
                RemovalSet.add(book)
    if args.get('price-less-than') is not None:
        for book in resBooks:
            if book.price > int(args.get('price-less-than')):
                RemovalSet.add(book)
    if args.get('year-bigger-than') is not None:
        for book in resBooks:
            if book.year < int(args.get('year-bigger-than')):
                RemovalSet.add(book)
    if args.get('year-less-than') is not None:
        for book in resBooks:
            if book.year > int(args.get('year-less-than')):
                RemovalSet.add(book)
    if args.get('genres') is not None:
        for book in resBooks:
            if not any(item in args.get('genres').split(',') for item in book.genres):
                RemovalSet.add(book)

    for item in RemovalSet:
        resBooks.discard(item)
    return resBooks


@app.route('/books', methods=['GET'])
def GetBooksData():
    args = request.args.to_dict()
    genres = args.get('genres')
    if genres is not None:
        genres = genres.split(',')
        if not all(genre.isupper() for genre in genres):
            return jsonify({'error': 'Wrong case for genres'}), 400
    resBooks = FilterBooks(args, set(BooksList.copy()))
    jsonBooksArr = [book.to_dict() for book in resBooks]
    jsonBooksArr = sorted(jsonBooksArr, key=lambda x: x['title'])

    log_message_info = f'Total Books found for requested filters is {len(resBooks)}'
    books_logger.info(log_message_info, extra={'request_num': request_num})
    return {'result': jsonBooksArr}, 200


@app.route('/book', methods=['GET'])
def GetSingleBookData():

    global request_num
    BookID = int(request.args.get('id'))
    for book in BooksList:
        if book.id == BookID:
            bookJson = book.to_dict()
            log_message_debug = f'Fetching book id {BookID} details'
            books_logger.debug(log_message_debug, extra={'request_num': request_num})
            return {'result': bookJson}, 200

    answer = {'errorMessage': f'Error: no such Book with id {BookID}'}
    books_logger.error(answer['errorMessage'], extra={'request_num': request_num})
    return answer, 404


@app.route('/book', methods=['PUT'])
def UpdateBookPrice():
    bookID = request.args.get('id')
    try:
        bookID = int(bookID)
        bookItem = BooksList[bookID-1]
        if int(request.args.get('price')) <= 0:
            answer = {'errorMessage': f"Error: price update for book {bookID} must be a positive integer"}
            books_logger.error(answer['errorMessage'], extra={'request_num': request_num})
            return answer, 409
        log_message_info = f"Update Book id [{bookID}] price to {request.args.get('price')}"
        books_logger.info(log_message_info, extra={'request_num': request_num})
        oldPrice = bookItem.price

        log_message_debug = f"Book [{bookItem.title}] price change: {oldPrice} --> {request.args.get('price')}"
        books_logger.debug(log_message_debug, extra={'request_num': request_num})

        bookItem.price = int(request.args.get('price'))
        return jsonify({'result': oldPrice}), 200
    except IndexError:
        answer = {'errorMessage': f"Error: no such Book with id {bookID}"}
        books_logger.error(answer['errorMessage'], extra={'request_num': request_num})
        return answer, 404


@app.route('/book', methods=['DELETE'])
def DeleteBook():
    bookID = int(request.args.get('id'))
    for book in BooksList:
        if book.id == bookID:
            log_message_info = f'Removing book [{book.title}]'
            books_logger.info(log_message_info, extra={'request_num': request_num})
            BooksList.remove(book)
            log_message_debug = f"After removing book [{book.title}] id: [{book.id}] there are {len(BooksList)} books in the system"
            books_logger.debug(log_message_debug, extra={'request_num': request_num})
            return jsonify({'result': len(BooksList)}), 200

    answer = {'errorMessage': f"Error: no such Book with id {bookID}"}
    books_logger.error(answer['errorMessage'], extra={'request_num': request_num})
    return answer, 404


@app.route('/logs/level', methods=['GET'])
def GetLoggerCurrLevel():
    loggerName = request.args.get('logger-name')
    if loggerName is not None:
        logger = logging.getLogger(loggerName)
        return logging.getLevelName(logger.level), 200

    else:
        return "Error: None query parameter passed ", 404


@app.route('/logs/level', methods=['PUT'])
def SetLoggerLevel():
    loggerName = request.args.get('logger-name')
    loggerLevel = request.args.get('logger-level')
    if loggerName is not None and loggerLevel is not None:
        logger = logging.getLogger(loggerName)
        logger.setLevel(loggerLevel)
        return logging.getLevelName(logger.level), 200
    else:
        return 'Error: one or more query parameters is None', 404


if __name__ == '__main__':
    app.run(debug=True, port=8574)
