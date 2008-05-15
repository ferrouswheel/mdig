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
