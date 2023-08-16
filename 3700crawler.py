#!/usr/bin/env python3

import argparse
import socket
import ssl
import gzip
from html.parser import HTMLParser
from time import time
import queue
from threading import Thread

DEFAULT_SERVER = "proj5.3700.network"
DEFAULT_PORT = 443

# PARSER CLASS EXTENDS HTMLPARSER TO READ/GRAB LINKS/FLAGS
class Parser(HTMLParser):
    
    # INIT 
    def __init__(self):
        super().__init__()
        
        # LIST OF ALL LINKS FOUND
        self.found = set()
        # QUEUE OF LINKS TO BE VISITED
        self.links = queue.Queue()
        # BOOL TO GRAB DATA WHEN FLAG TAG IS FOUND
        self.get_data = False
        # LIST OF FLAGS
        self.flags = []
        
        # len(flags) < 5 ?
        self.searching = True
        # LAST LINK RECEIVED BY FEED
        self.latest_link = '/'
        # ERROR LINKS FOR DEBUGGING
        self.error_links = []
    
    # CALLS SUPER FEED METHOD, LOGS FAILURES
    def feed(self, html, link, sockid):
        self.latest_link = link
        try:
            super().feed(html)
        except Exception as e:
            # Re-add failed link just in case
            self.links.put(self.latest_link)
            self.error_links.append(self.latest_link)
            
    # SEARCHES ALL A AND H2 TAGS FOR LINKS/FLAG CLASS
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            link = attrs[0][1]
            # ENSURE LINK IS A USERS HOME AND NOT FRIENDS PAGE
            if link.find('/fakebook/') > -1:
                if link.find('friends') == -1:
                    if link not in self.found:
                        self.links.put(link)
                        self.found.add(link)
                        
        # CHECK IF CLASS IS SECRET FLAG
        if tag == 'h2':
            for attr in attrs:
                if attr == ('class', 'secret_flag'):
                    # GRAB NEXT DATA
                    self.get_data = True

    # HANDLES END TAGS WHEN GET_DATA IS TRUE TO FIND FLAG
    def handle_endtag(self, tag):
        if self.get_data and tag == 'h2':
            # CHECK FOR REPEAT FLAG
            if self.latest not in self.flags:
                # RESET GET_DATA
                self.get_data = False
                # GRAB FLAG VALUE
                flag = self.latest[6:]
                
                # PRINT AND ADD FLAG
                print(flag)
                self.flags.append(flag)
            # CHECK IF ALL FLAGS ARE FOUND
            if len(self.flags) == 5:
                self.searching = False

    # GRAB DATA (FLAG) WHEN GET_DATA IS TRUE
    def handle_data(self, data):
        if self.get_data:
            self.latest = data

# ATTEMPT TO GRAB HTML STRING FROM RESPONSE, RETURN RESPONSE ON FAIL
def get_html(response):
    s = response.find('<html')
    if s == -1:
        return response
    f = s + response[s:].find('</html>') + 7
    return response[s:f]
            
# HELPER FOR GETTING VALUE BETWEEN START AND END SUBSTR
def finder(response, start, end):
    s = response.find(start)
    if s == -1:
        return s
    s += len(start)
    f = s + response[s:].find(end)
    return response[s:f]

# GET SESSIONID FROM SET-COOKIES IN RESPONSE
def get_sid(response):
    sid = finder(response, 'sessionid=',';')
#    print('sessionid:',sid)
    return sid

# GET CSRFTOKEN FROM SET-COOKIES IN RESPONSE
def get_csrf(response):
    csrf = finder(response, 'csrftoken=',';')
#    print('csrftoken:',csrf)
    return csrf

# GET CSRFMIDDLEWARE TOKEN
def get_csrfmiddleware(response):
    csrf_mid = finder(response, 'csrfmiddlewaretoken" value="','"')
#    print('csrfmiddlewaretoken:',csrf_mid)
    return csrf_mid

# GET PAGECOUNT FROM RESPONSE
def get_pagecount(response):
    return int(finder(response, 'Page 1 of ', '\n'))

# GET URL FROM REQUEST
def get_url(request):
    if request[0:4] == 'POST':
        start = 'POST '
    else:
        start = 'GET '
    return finder(request, start, ' ')

# GET LOCATION HEADER VALUE FOR 503 RESPONSE CODES
def get_loc(response):
    return finder(response, 'Location: ', '\n')
     
# CONVERT TIME IN S TO MINUTES:SECONDS STRING
def get_time_m_s(s):
    m = int(s/60)
    rs = s%60.0
    return '{}m{}s'.format(m,int(rs))
    
# MY WEBCRAWLER
class Crawler:
    def __init__(self, args):
        self.server = args.server
        self.port = args.port
        self.username = args.username
        self.password = args.password
        
        # SET TLS MODE TO TRUE
        self.tls = True
        
        # PARSER TO PARSE RESPONSES FOR FLAGS/LINKS
        self.parser = Parser()
        
        # 5 SOCKETS FOR EACH THREAD
        self.mysocket = [None,None,None,None,None]
        
        # DEBUG SECTION
        
        # DEBUG?
        self.debug = True
        
        # TRACK USERS VISITED/ SITES VISITED
        self.users = 0
        self.last_users = 0
        self.visited = 0
        
        # TRACK STARTING TIME
        self.start_time = 0
        
    # GET CURRENT TIME FOR TRACKING
    def get_time(self):
        return (time() - self.start_time)
        
    # OPEN SOCKET AT GIVEN SOCKET ID, RETRY ON FAILURE
    def open_socket(self,sockid):
        try:
            mysocket = socket.socket(socket.AF_INET, 
                                     socket.SOCK_STREAM)

            mysocket.connect((self.server, self.port))

            if self.tls:
                context = ssl.create_default_context()
                mysocket = context.wrap_socket(mysocket, server_hostname=self.server)
        except Exception as e:
            #if self.debug:
            #    print('Failed to open socket',sockid)
            self.open_socket(sockid)
            
        self.mysocket[sockid] = mysocket
    
    # CLOSE SOCKET AT GIVEN SOCKET ID
    def close_socket(self, sockid):
        self.mysocket[sockid].close()
        
    # MAKE ATTEMPT TO SEND REQUEST TO SERVER, RETRY ON FAIL
    def send(self, sockid, request, login):
        try:
            return self.try_send(sockid, request, login)
        except Exception as e:
            #if self.debug:
            #    print('RETRY SEND',sockid)
            #    print('Error:',e)
            return self.try_send(sockid, request, login)
            
    # SEND REQUEST TO SERVER, PROCESS RESPONSE
    def try_send(self, sockid, request, login):
            
        # OPEN SOCKET
        self.open_socket(sockid)
        mysocket = self.mysocket[sockid]
        
        # SEND REQUEST
        mysocket.send(request.encode('ascii'))

        # RECEIVE FIRST CHUNK
        chunk = mysocket.recv(1000)
        # CHECK IF GZIP ENCODED RESPONSE, DECODE
        use_gzip = chunk.find(b'gzip') != -1
        if use_gzip:
            i = chunk.find(b'\r\n\r\n') + 4
            data = chunk[:i].decode('ascii')
            content = chunk[i:]
        else:
            data = chunk.decode('ascii')
            
        # FIND CONTENT LENGTH
        content_length = int(finder(data, 'Content-Length: ', '\n'))
        
        # READ MORE IF NECESSARY, AND DECODE
        if content_length > len(data):
            chunk = mysocket.recv(content_length)
            if use_gzip:
                content += chunk
                data += gzip.decompress(content).decode('ascii')
            else:
                data += chunk.decode('ascii')
        response = data
        
        # CLOSE SOCKET
        self.close_socket(sockid)
        
        # DEBUG INFO
        if self.debug and self.users - self.last_users >= 100:
            self.print_info()
            
        # GET CODE FROM RESPONSE
        code = response[9:12]
        
        # PROCESS RESPONSE WITH CODE
        return self.process_code(code, sockid, request, response, login)
    
    # PROCESS RESPONSE BASED ON CODE
    def process_code(self, code, sockid, request, response, login):
        # IF BAD CODE OR NOT LOGIN
        # DONT WANT TO PROCESS IF LOGGING IN
        if code != '200' and not login:
            # REDIRECT, RESEND AT NEW URL
            if code == '302':
                oldurl = get_url(request)
                newurl = get_loc(response[:1000])
                return self.try_send(sockid, request.replace(oldurl,newurl), login)
            # NOT FOUND, DO NOTHING
            elif code == '403' or code == '404':
                pass
            # SERVER FAILURE, RESEND
            elif code == '503':
                return self.try_send(sockid, request, login)
            
        # RETURN SERVER HTML RESPONSE IF NOT LOGIN
        if not login:
            return get_html(response)
        else:
            # POST GRABS COOKIES FROM RESPONSE, DONT WANT HTML
            return response
    
    # PRINT DEBUG INFO
    def print_info(self):
        self.last_users = self.users
        time = self.get_time()
        remaining = self.parser.links.qsize()
        print('\nCurrent time:   ',get_time_m_s(time))
        print('Pages Visited:  ',self.visited)
        print('Users Visited:  ',self.users)
        print('Remaining Users:',remaining)
        print('Speed (ups):    ',self.users/time)
        if self.users > 0:
            print('Estimated time remaining: ', get_time_m_s(remaining * time/self.users))
        print()
    
    # BUILD AND SEND POST REQUEST
    def post(self, request, headers, payload):
        headers.insert(0,'Host: proj5.3700.network')
        headers.insert(1,'Connection: close')
        request = request + '\n'
        request += '\n'.join(headers)
        request += '\n\r\n' + payload + '\r\n\r\n'
        
        return self.send(0,request, login=True)
    
    # BUILD AND SEND GET REQUEST
    def get(self, sockid, request, headers=None, login=False):
        request = request + '\n'
        if headers:
            headers.insert(0,'Host: proj5.3700.network')
            headers.insert(1, 'Connection: close')
            headers.insert(2, 'Accept-Encoding: gzip')
            request += '\n'.join(headers) + '\n'
        request += '\r\n\r\n'
        
        return self.send(sockid, request, login)
    
    # LOGIN TO SERVER WITH POST
    def login(self):
        
        # GET INITIAL COOKIES
        request = "GET /accounts/login/?next=/fakebook/ HTTP/1.0"
        response = self.get(0,request,login=True)
        
        sid = get_sid(response)
        csrf = get_csrf(response)
        csrf_mid = get_csrfmiddleware(response)
        
        # ADD HEADERS
        headers = []
        headers.append("Cookie: sessionid=" + sid  + "; csrftoken=" + csrf)
        headers.append('Content-Type: application/x-www-form-urlencoded')
        
        # FORM POST PAYLOAD
        payload = "username=" + self.username + "&password=" + self.password + "&csrfmiddlewaretoken=" + csrf_mid + "&next=''"
        
        headers.append('Content-Length: ' + str(len(payload)))
        
        request = "POST /accounts/login/?next=/fakebook/ HTTP/1.1"
        
        response = self.post(request, headers, payload)
        
        # RETURN SESSION COOKIES
        return get_sid(response), get_csrf(response)
        
    # RUN CRAWLER
    def run(self):
        
        # OPEN SOCKET 0 FOR INITIAL LOGIN/HOMEPAGE SEARCH
        self.open_socket(0)
        
        # LOGIN
        sid, csrf = self.login()
        
        # SET SESSIONID AND CSRFTOKEN
        if sid == -1 or csrf == -1:
            sid, csrf = self.login()
        self.sid = sid
        self.csrf = csrf
        
        # TRACK START TIME
        self.start_time = time()
        
        # SEARCH HOMEPAGE FOR FIRST FEW LINKS
        self.search_homepage()

        # THREADING
        threads = []
        
        # MAKE THREADS
        for i in range(5):
            threads.append(Thread(target=self.task, args=(i,)))
        
        # START THREADS
        for thread in threads:
            thread.start()
        # WAIT FOR THREADS
        for thread in threads:
            thread.join()
        
        # PRINT FINAL DEBUG INFO
        if self.debug:
            # PRINT INFO ABOUT SEARCH
            print('Time taken:',get_time_m_s(self.get_time()))
            print('Sites visited:', len(self.parser.found))
            print('Error links:')
            for l in self.parser.error_links:
                print(l)
            print('\nFLAGS:')
            
            # PRINT TO FILE
            secret_flags = open('secret_flags', 'w')
            for flag in self.parser.flags:
                print(flag)
                secret_flags.write(flag + '\n')
            secret_flags.close()
        
    # TASK FOR EACH THREAD, GET LINK FROM QUEUE AND
    # VISIT ALL HOMEPAGE AND FRIEND PAGES
    def task(self, sockid):
        try:
            # LOOP WHILE NOT ALL FLAGS ARE FOUND
            size = self.parser.links.qsize()
            while self.parser.searching:
                link = self.parser.links.get()
                self.visit(sockid, link)
                self.users += 1
                size = self.parser.links.qsize()
        except:
            # ON ANY FAILURE RESTART TASK AND RETRY LINK
            self.parser.links.put(link)
            self.task(sockid)
        
    # VISIT A USERS FRIENDS PAGE, AT PAGE "page"
    def get_friends(self, sockid, account_link, page):
        # BUILD REQUEST AND HEADERS
        request = "GET {}friends/{}/ HTTP/1.1".format(account_link, page)
        headers = []
        headers.append("Cookie: sessionid={}; csrftoken={}".format(self.sid, self.csrf))
        
        # SEND GET AND FEED RESPONSE TO PARSER
        response = self.get(sockid, request, headers)
        self.parser.feed(response, request[4:35], sockid)
        
        return response
      
    # VISIT ALL PAGES ASSOCIATED WITH A USER
    def visit(self, sockid, account_link):
        # BUILD REQUEST AND HEADERS
        request = "GET {} HTTP/1.1".format(account_link)
        headers = []
        headers.append("Cookie: sessionid={}; csrftoken={}".format(self.sid, self.csrf))
        
        # VISIT USER HOMEPAGE, PARSE
        response = self.get(sockid, request, headers, True)
        self.parser.feed(response, account_link, sockid)
        self.visited += 1
        
        # VISIT USER FRIENDS PAGE 1, PARSE
        response = self.get_friends(sockid, account_link, 1)
        self.visited += 1
        # GET PAGECOUNT
        pagecount = get_pagecount(response)
        # LOOP FOR EACH FRIENDS PAGE
        for i in range(1, pagecount):
            page = i + 1 
            self.get_friends(sockid, account_link, page)
            self.visited += 1
        
    # GET LINKS FROM HOMEPAGE
    def search_homepage(self):
        # BUILD REQUEST AND HEADERS
        request = "GET /fakebook/ HTTP/1.1"
        headers = []
        headers.append('Host: proj5.3700.network')
        headers.append("Connection: close")
        headers.append("Cookie: sessionid=" + self.sid  + "; csrftoken=" + self.csrf)
        
        response = self.get(0, request, headers, True)
        self.parser.feed(get_html(response), '/facebook/', 'X')
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='crawl Fakebook')
    parser.add_argument('-s', dest="server", type=str, default=DEFAULT_SERVER, help="The server to crawl")
    parser.add_argument('-p', dest="port", type=int, default=DEFAULT_PORT, help="The port to use")
    parser.add_argument('username', type=str, help="The username to use")
    parser.add_argument('password', type=str, help="The password to use")
    args = parser.parse_args()
    sender = Crawler(args)
    sender.run()
