import logging
import lxml

class Region:
    
    def __init__(self, node):
        self.log = logging.getLogger("mdig.region")
        self.xml_node = node
        self.id = self.xml_node.attrib["id"]
    
    def get_name(self):
        if "name" in self.xml_node.attrib.keys():
            index = self.xml_node.attrib["name"].find('@')
            if index == -1:
                return self.xml_node.attrib["name"]
            return self.xml_node.attrib["name"][:index]
        else:
            return None

    def get_mapset(self):
        if "name" in self.xml_node.attrib.keys():
            index = self.xml_node.attrib["name"].find('@')
            if index == -1: return None
            return self.xml_node.attrib["name"][index+1:]
        else:
            return None
        
    def set_name(self, new_name):
        self.xml_node.attrib["name"] = new_name
    
    def get_resolution(self):
        res_node = self.xml_node.xpath('resolution')
        if len(res_node) == 1:
            return float(res_node[0].text)
        else:
            if self.get_name() is not None: return None
            else: return 1
            
    def set_resolution(self, res):
        res_node = self.xml_node.xpath('resolution')
        if len(res_node) == 0:
            res_node = lxml.etree.SubElement(self.xml_node,'resolution')
        else:
            res_node = res_node[0]
        res_node.text = repr(float(res))
        
    def get_extents(self):
        ext_node = self.xml_node.xpath('extents')
        if len(ext_node) == 1:
            extents = dict(ext_node[0].attrib)
            for i in extents: extents[i] = float(extents[i])
            return extents
        else:
            self.log.debug("Region has no unique extent node")
            return None
        
    def set_extents(self, ext):
        ext_node = self.xml_node.xpath('extents')
        if len(ext_node) == 0:
            ext_node = lxml.etree.SubElement(self.xml_node,'extents')
        else:
            ext_node = ext_node[0]
        for i in ext:
            if i not in ['n','s','e','w']:
                raise KeyError('extent keys must be one of n,s,e,w')
        for i in ext:
            ext_node.attrib[i] = str(ext[i])
        
    def __str__(self):
        x = "mdig.Region "
        name = self.get_name()
        e = self.get_extents()
        r = self.get_resolution()
        if name is not None:
            x += "saved region '%s' " % name 
        if e is not None:
            x += "extents %s " % str(e) 
        if r is not None:
            x += "resolution %f " % float(r) 

    def update_xml(self):
        pass
