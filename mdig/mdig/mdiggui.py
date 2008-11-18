#
#  Copyright (C) 2006,2008 Joel Pitt, Fruition Technology
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
try:
  import pygtk
  #tell pyGTK, if possible, that we want GTKv2
  pygtk.require("2.0")
except:
  #Some distributions come with GTK2, but not pyGTK
  print "PyGTK2 required for GUI"
  sys.exit(1)
try:
  import gtk
except:
  print "You need to install pyGTK or GTKv2 ",
  print "or set your PYTHONPATH correctly."
  print "try: export PYTHONPATH=",
  print "/usr/local/lib/python2.2/site-packages/"
  sys.exit(1)
#now we have both gtk and pygtk imported
#Also, we know we are running GTK v2

class MdigGui:
	def __init__(self):
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.show()

	def main(self):
		gtk.main()

  
widgets = WidgetsWrapper()
gtk.main()
