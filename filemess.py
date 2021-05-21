#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
MIT but blocked License (5 years)
Copyright (c) 2019 Florian Steenbuck

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice can not be applied to persons, organizations or
other legal entities that are have or had in the last 5 years a sponsorship,
a cooperation or other legal relation to one of, or be one of, the following
persons, organizations or other legal entities.

Vodafone Group Plc
Vodafone Global Enterprise Limited
Bluefish Communications
Vodafone Automotive SpA
Deutsche Post AG
Linde plc
Unilever plc
Unilever N.V.
Volkswagen Group
SHAKEN not STIRRED Consulting GmbH & Co. KG
André Firmenich
Jörg Staggenborg
Marcel Lange
Daniela Engelke
hsp Handels-Software-Partner GmbH
Paul Liese
Etribes Connect GmbH
Laura Prym
Lukas Höft
Marcel Sander
Dustin Lundt
Yara Molthan
Nils Seebach
Fabian J. Fischer
Arne Stoschek
Stefan Luther
gastronovi GmbH
Christian Jaentsch
Bartek Kaznowski
Andreas Jonderko
Karl Jonderko
Erika Witting
Ludger Ey

They got no rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software. They do not got permission to deal in anyway with
the Software or Software Source Code.

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from threading import Thread
from Queue import Queue
import sys
import socket
from os.path import isdir
from os.path import isfile
from os.path import join as pjoin
from os import mkdir, listdir
import logging

def obtain_thread(args, me, path):
    args = list(args)
    args.append(me)
    args.append(path)
    return ObtainThread(*tuple(args))

class RootObtainer():
    def __init__(self, ip, range_):
        self._threads = []
        self._open_threads = Queue()
        for port in range_:
            self._open_threads.put((ip, port))
        first_args = self._open_threads.get()
        first_thread = obtain_thread(first_args, self, ".")
        first_thread.start()
        self._threads.append(first_thread)
        self._tasks = Queue()

    def run(self):
        while True:
            item = self._tasks.get()
            if type(item) == tuple:
                typ, path = item
                open_thread = self._open_threads.get()
                thread = obtain_thread(open_thread, self, path)
                logging.info(typ+" "+path)
                thread.start()
                self._threads.append(thread)

    def free_thread(self, ip, port):
        self._open_threads.put((ip, port))

    def init_end(self):
        self._tasks.put("end")

    def add_dir(self, path):
        self._tasks.put(("d", path))

    def add_file(self, path):
        self._tasks.put(("f", path))


class ObtainThread(Thread):
    def __init__(self, ip, port, root, path):
        self._ip = ip
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._root = root
        self._path = path
        self._firstline = bytes("")
        self._type = bytes("")
        self._len = None
        self._data = bytes("")
        Thread.__init__(self)

    def run(self):
        self._sock.sendto(self._path, (self._ip, self._port))
        len_ = 1024
        while True and ((type(self._len) != int) or (type(self._len) == int and self._len > 0)):
            obtain_data = type(self._len) == int
            data, addr = self._sock.recvfrom(len_)
            if not obtain_data:
                type_split = data.split("\n", 1)
                if len(type_split) > 1:
                    self._firstline += type_split[0]
                    self._data += type_split[1]
                    if self._firstline.startswith("file"):
                        self._type = "file"
                        self._len = int(self._firstline[4:])
                    elif self._firstline.startswith("dir"):
                        self._type = "dir"
                        self._len = int(self._firstline[3:])
                    self._len -= len(self._data)
                else:
                    self._firstline += data
            else:
                self._data += data
                self._len -= len(self._len)
        if self._type == "file":
            file = open(self._path, "w+")
            file.write(self._data)
            file.close()
        elif self._type == "dir":
            entries = self._data.split("\n")
            if entries != [""]:
                for entry in entries:
                    typ = entry[0]
                    name = entry[1:]
                    path = pjoin(self._path, name)
                    if typ == "f":
                        self._root.add_file(path)
                    elif typ == "d":
                    	if not isdir(path):
                            mkdir(path)
                        self._root.add_dir(path)
        self._root.free_thread(self._ip, self._port)


def obtain(ip, range_):
    RootObtainer(ip, range_).run()

class ServeClientThread(Thread):
    def __init__(self, ip, port, data):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._ip = ip
        self._port = port
        self._datas = Queue()
        self._datas.put(data)
        self._data = bytes("")
        Thread.__init__(self)

    def run(self):
        while True:
            data = self._datas.get()
            firstline_split = data.split("\n", 1)
            if len(firstline_split) > 0:
                self._data += firstline_split[0]
                break
            else:
                self._data += data
        if isfile(self._data):
            file = open(self._data, "r")
            content = file.read()
            file.close()

            data = bytes("file"+str(len(content))+"\n")+content
            while len(data) > 0:
                 self._sock.sendto(data[:1024], (self._ip, self._port))
                 data = data[1024:]
        elif isdir(self._data):
            entries = []
            for name in listdir(self._data):
                if name in [".",".."]:
                    continue
                entry = ""
                path = pjoin(self._data, name)
                if isfile(path):
                    entry = "f"
                elif isdir(path):
                    entry = "d"
                else:
                    continue
                entry += name
                entries.append(entry)
            
            content = "\n".join(entries)
            data = bytes("dir"+str(len(content))+"\n")+content
            while len(data) > 0:
                self._sock.sendto(data[:1024], (self._ip, self._port))
                data = data[1024:]

    def add_data(self, data):
        self._datas.put(data)

class ServeThread(Thread):
    def __init__(self, ip, port):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._ip = ip
        self._port = port
        self._clients = {}
        Thread.__init__(self)

    def run(self):
        self._sock.bind((self._ip, self._port))
        len_ = 1024
        while True:
            data, addr = self._sock.recvfrom(len_)
            ip, port = addr
            id_ = str(ip)+":"+str(port)
            if not id_ in self._clients.keys():
                self._clients[id_] = ServeClientThread(ip, port, data)
                self._clients[id_].start()
            else:
                self._clients[id_].add_data(data)

def serve(ip, range_):
    servis = []
    for port in range_:
        servi = ServeThread(ip, port)
        servi.start()
        servis.append(servi)
    return servis

def input_type(in_, typ):
    result = None
    while type(result) != typ:
        result = input(in_)
    return result

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("start")
    cmd = None
    ip = None
    range_ = None

    begin = None
    end = None

    args = sys.argv[1:]
    if len(args) > 0:
        cmd = args[0]
    if len(args) > 1:
        ip = args[1]
    if len(args) > 2:
        try:
            begin = int(args[2])
        except:
            begin = None
    if len(args) > 3:
        try:
            end = int(args[3])
        except:
            end = None

    while (type(cmd) != str) and (not cmd in ["obtain","serve"]):
        cmd = input("Command (obtain/serve): ")

    while True:
        if begin is None:
            begin = input_type("Begin (int): ", int)
        if end is None:
            end = input_type("End (int): ", int)
        try:
            range_ = range(begin, end)
            break
        except:
            begin = None
            end = None
            pass
    logging.info(cmd)
    vars()[cmd](ip, range_)