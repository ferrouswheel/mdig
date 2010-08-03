#!/usr/bin/env python
#
#  Copyright (C) 2008 Joel Pitt, Fruition Technology
#
#  This file is part of Modular Dispersal In GIS.
#
#  Modular Dispersal In GIS is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your
#  option) any later version.
#
#  Modular Dispersal In GIS is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#  Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with Modular Dispersal In GIS.  If not, see <http://www.gnu.org/licenses/>.
#

from Tkinter import *
import os.path
import sys
from PIL import Image

try:
    import ImageWin
    # make sure we can create DIBs
    dib = ImageWin.Dib("L", (1, 1))
except (ImportError, AttributeError):
    ImageWin = None

if ImageWin:
	from ImageWin import Dib, HWND
	class ImageView(Frame):

	    def __init__(self, master, **options):
		Frame.__init__(self, master, **options)
		self.dib = None
		self.bind("<Expose>", self._expose)

	    def setimage(self, image):
		self.config(bg="") # don't update the background
		self.dib = Dib(image.convert('RGB'))
		self.master.configure(width=self.dib.size[0],height=self.dib.size[1])
		self.configure(width=self.dib.size[0],height=self.dib.size[1])
		self.pack()
		self.event_generate("<Expose>")

	    def _expose(self, event):
		if self.dib:
		    self.dib.expose(HWND(self.winfo_id()))
else:
    from ImageTk import PhotoImage
    class ImageView(Frame):

	def __init__(self, master, **options):
	    Frame.__init__(self, master, **options)
	    self.view = Label(self)
	    self.view.place(relwidth=1, relheight=1)
	    self.pack(side=LEFT,fill=BOTH,expand=YES)

	def setimage(self, image):
	    photo = PhotoImage(image)
	    self.view.config(image=photo)
	    self.view.photo = photo # keep a reference!
	    self.configure(width=image.size[0],height=image.size[1])
	    self.pack(side=LEFT,fill=BOTH,expand=YES)

# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/82965
# make a function that periodically checks file.
# calls self.master.after(100, function)

class PngView:
    """
    Launch the main part of the GUI and the worker thread. periodicCall and
    endApplication could reside in the GUI part, but putting them here
    means that you have all the thread controls in a single place.
    """
    def __init__(self, master, fname):
	"""
	Start the GUI and the asynchronous threads. We are in the main
	(original) thread of the application, which will later be used by
	the GUI. We spawn a new thread for the worker.
	"""
	self.master = master
	self.fname = fname
	self.last_time = 0

	self.do_update = True

	# Set up the GUI part
	self.master.title("MDiG simulation")
	self.gui = ImageView(master,width=100,height=100)
	self.gui.pack()

	# Set up the thread to do asynchronous I/O
	# More can be made if necessary
	self.running = 1

	# Start the periodic call in the GUI to check if the queue contains
	# anything
	self.periodicCall()

    def periodicCall(self):
	"""
	Check every 100 ms if png has changed
	"""
	try:
	    new_time = os.path.getmtime(self.fname)
	except os.error:
	    sys.exit()

	if new_time > self.last_time:
	    self.loadFile(self.fname)
	    self.last_time = new_time

	if not self.running:
	    # This is the brutal stop of the system. You may want to do
	    # some cleanup before actually shutting it down.
	    sys.exit(1)
	self.master.after(100, self.periodicCall)

    def loadFile(self, fn):
	my_image = Image.open(fn)
	self.gui.setimage(my_image)

    def endApplication(self):
	self.running = 0

root = Tk()

viewer = PngView(root,sys.argv[1])
root.mainloop()

# use subprocess module to create new process.
