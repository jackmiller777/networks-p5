miller.john 
README.md
3700 Proj 5

In this file, you should briefly describe your high-level approach, any challenges you faced, and an overview of how you tested your code.

High-level approach:
I started by playing around with the starter code, and by adding ssl as well as HTTP1.1. I slowly tried to build up a login, and had a lot of trouble. Once I figured that out, I wanted to see what sort of data I'd be dealing with so I played around a lot with keep-alive, gzip, threading and processing responses. I had trouble getting keep-alive to work, so I gave up on it. Finally, I organized and labeled my code to be more neat. 

The end result goes something like this:
Login
Read initial user links from home page
Build queue of these links
Start 5 threads
In each thread:
    Get user link from queue
    Search link for flags / links
    Search friends list for flags / new links
    For each search, create socket and connect, request and receive gzip encoded response, close on finish
    Print flags when found in parser
    When all flags are found, quit

Challenges:
The most difficult part of this project for me was figuring out how to login. I spent a lot of time trying and failing with various csrftokens and session ids until eventually I did some more research and figured out how forms/headers/cookies actually work. I could have wasted less time by gaining a better understanding of HTTP requests and responses before diving in and messing around with the starter code. I also had trouble implementing keep-alive, likely because I didn't calculate the correct receive size from the content-length. I didn't spend to much time on it and decided not to implement it

Testing:
I tested my program mostly by just running it on the server with lots of debug info being printed out as it was running, many, many times.
