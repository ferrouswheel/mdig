import time
import re
import xml.dom.minidom
from scipy.io import read_array
from numpy import vstack, concatenate, random, array

import GRASSInterface

class TVgenerator(list):
    def __init__(self, parameters, expressions, TMsize):
        self.TMsize = TMsize
        self.parameters = parameters
        expressionList = []
        pattern = re.compile(r'''
                            #Don't specify matching beginning of string (no ^)
        \s*                 #matches any number of whitespaces         
        (\w*)               #matches any number (zero or more) of alphanumeric characters (parameter name)
        \s*                 #matches any number of whitespaces         
        ([/+/-/*//]?)       #Match any mathematical operators (optional)
        \s*                 #matches any number of whitespaces         
        (\w*)               #matches any number (zero or more) of alphanumeric characters (parameter name)
        \s*                 #matches any number of whitespaces         
        ([/+/-/*//]?)       #Match any mathematical operators (optional)
        \s*                 #matches any number of whitespaces         
        (\w*)               #matches any number (zero or more) of alphanumeric characters (parameter name)
        \s*                 #matches any number of whitespaces         
        ([/+/-/*//]?)       #Match any mathematical operators (optional)
        \s*                 #matches any number of whitespaces         
        (\w*)               #matches any number (zero or more) of alphanumeric characters (parameter name)
        \s*                 #matches any number of whitespaces         
        ([/+/-/*//]?)       #Match any mathematical operators (optional)
        \s*                 #matches any number of whitespaces         
        (\w*)               #matches any number (zero or more) of alphanumeric characters (parameter name)
        \s*                 #matches any number of whitespaces         
        ([/+/-/*//]?)       #Match any mathematical operators (optional)
        \s*                 #matches any number of whitespaces         
        (\w*)               #matches any number (zero or more) of alphanumeric characters (parameter name)
        \s*                 #matches any number of whitespaces         
        ([/+/-/*//]?)       #Match any mathematical operators (optional)
        \s*                 #matches any number of whitespaces         
        (\w*)               #matches any number (zero or more) of alphanumeric characters (parameter name)
                ''', re.VERBOSE)
        for i in expressions:               
            expressionTemp = pattern.search(i).groups()
            tempExpList = []
            goBetweenList = []

            #remove blank groups from parsing, move expression elements to a
            # list (tempExpList)
            for j in expressionTemp:
                if j !='':
                    tempExpList.append(j)
                    
            for g in tempExpList:
                #if expression element is a parameter, add 'genVal' syntax
                if parameters.has_key(g):
                    tempString = "self.parameters['%s'].genVal(%s, coords)" % (g, "%(indexValue)i")
                    goBetweenList.append(tempString)
                else:
                    goBetweenList.append(g)
                    
            # combines elements of tempExpList into a single string and adds them
            # to the expressionList
            self.append(''.join(goBetweenList))

    def buildMatrix(self, indexValue, coords):
        TVlist = []
        for i in range(len(self)):
            TVal = self[i] % vars()
            TVlist.append(eval(TVal))
        TM = array(TVlist)
        TM = TM.reshape(self.TMsize, self.TMsize)
        return TM 

class paramGenerator(list):
    """Generates parameters which produce either static or random values; source specified in xml file"""
    def __init__(self, source, index, dist, vals):
        self.data = [0]
        self.source = source
        try:
            if source == 'map':
                self.mapName = str(vals[0])
                mapRange = rasterIO_2.getRange()
                nRows = int(mapRange[8][6:])
                nCols = int(mapRange[9][6:])
                cmd = "r.out.ascii -h input=%s" %(self.mapName)
                p = grass.pipe_command(cmd)
                self.mat = numpy.matrix(p.communicate()[0])
                self.mat = self.mat.reshape((nRows,nCols))
            if source == 'CODA':
                self.append(read_array(index))
                for i in range(len(vals)):
                    temp = read_array(vals[i])
                    if i == 0:
                        for j in range(len(self[0])):
                            self.append(temp[int(self[0][j,1])-1:int(self[0][j,2]),1])
                    else:
                        for j in range(len(self[0])):
                            self[j+1] = concatenate((self[j+1], temp[int(self[0][j,1]-1):int(self[0][j,2]), 1]))
            if source == 'random':
                self.str = ("(%s.%s(%f,%f))" %(source, dist, vals[0], vals[1]))
            if source == 'zero':
                pass
            if source == 'static':
                self.static = vals[0]
        except IOError:
            print '%s   %s   %s   %s parameter value source coding not valid' %(source, index, dist, vals)

    def genVal(self, indexValue, coords):
        """Draws a random CODA iteration from the range specified in index for the corresponding parameter level"""
        if self.source == 'CODA': return self[indexValue][random.random_integers(0,len(self[indexValue]))]
        if self.source == 'random': return eval(self.str)
        if self.source == 'zero': return 0
        if self.source == 'static': return self.static
        if self.source == 'map': return self.mat[coords[0], coords[1]]

class LifestageTransition:

    def __init__(self,xmlFile):
        # Timing of load process
        start_time = time.time()
        self.log = logging.getLogger("mdig.popmod")
        # XML parsing
        self.xml_dom = xml.dom.minidom.parse(xml_file)
        self.indexSource = self.xmlToIndex()
        # TODO initSource has to be replaced with the input maps from the various
        # lifestages
        self.initSource = self.xmlToInitialState()
        # Calcuate TMsize, used in defining/parsing 'expressions' list
        # TODO TMSize is the same as the number of lifestages
        TMsize = len(initSource)
        self.parameters = self.xmlToParam()
        self.expressions = self.xmlToExpressionList(TMsize)

        # determine size of rasters
        rangeData = getG().getRange()

        load_time = time.time() - start_time
        self.log.debug('Transition matrix set to %i x %i' % (TMsize, TMsize) )
        self.log.debug('Transition sources loaded.  Load time %f seconds'
                % load_time)

        #Create matrix instance
        self.TMatrix = TVgenerator3.TVgenerator(parameters, expressions, TMsize)

    def xmlToInitialState(self):
        rasterMaps = self.xml_dom.getElementsByTagName("raster")
        #print rasterMaps.childNodes[0].data
        initialStateMaps = []
        try:
            for i in rasterMaps:
                initialStateMaps.append(str(i.childNodes[0].data))
        except IndexError:
            print "Index Error - Blank initialState raster specification in XML file?"         
        return initialStateMaps

    def xmlToIndex(self):
        ControllerInput = self.xml_dom.firstChild
        habSource = ControllerInput.getElementsByTagName("indexMap")
        index = str(habSource[0].childNodes[0].data)
        return index

    def xmlToOutputFile(self):
        ControllerInput = self.xml_dom.firstChild
        outputFileSource = ControllerInput.getElementsByTagName("outputFile")
        outputFile = str(outputFileSource[0].childNodes[0].data)

        return outputFile

    def xmlToParam(self):
        ControllerInput = self.xml_dom.firstChild
        parameters = ControllerInput.getElementsByTagName("ParameterValue")
        paramDict = {}

        #for i in range(TMsize*TMsize):
        #    paramList.append(0)
        for i in parameters:
            parameter = str(i.getElementsByTagName('parameterName')[0].childNodes[0].data)
            source = str(i.getElementsByTagName('source')[0].childNodes[0].data)
            index = i.getElementsByTagName('index')
            if source=='CODA':
                index = str(index[0].childNodes[0].data)
            elif source=='map':
                index = None
            else:
                if str(index[0].childNodes[0].data) == 'None':
                    index = None
                else: index = int(index[0].childNodes[0].data)
            dist = i.getElementsByTagName('distribution')
            dist = str(dist[0].childNodes[0].data)
            valueList = []
            values = i.getElementsByTagName('d')
            for v in values:
                try:
                    if source == 'CODA':
                        valueList.append(str(v.childNodes[0].data))
                    if source == 'map':
                        valueList.append(str(v.childNodes[0].data))
                    else: valueList.append(float(v.childNodes[0].data))
                except: pass
            if i == parameters[0]:
                if source == 'CODA':
                    paramDict[parameter] = paramGenerator.paramGenerator(source, index, dist, valueList)
                else:
                    paramDict[parameter] = paramGenerator.paramGenerator(source, index, dist, valueList)
            else:
                paramDict[parameter]=(paramGenerator.paramGenerator(source, index, dist, valueList))
        
        return paramDict

    def xmlToExpressionList(self, TMsize):
        ControllerInput = xml_dom.firstChild
        
        expressions = ControllerInput.getElementsByTagName("expression")
        expressionList = []

        for i in range(TMsize*TMsize):
            expressionList.append(0)

        for i in expressions:
            position = i.getElementsByTagName('position')
            position = int(position[0].childNodes[0].data)
            formula = i.getElementsByTagName('formula')
            formula = str(formula[0].childNodes[0].data)
            
            if expressionList[position] == 0:
                expressionList[position] = formula
            else:
                expressionList[position].update(formula)
        
        return expressionList

    #Old transition reading from xml file
    def xmlToTList(self, TMsize):
        ControllerInput = self.xml_dom.firstChild
        
        transitions = ControllerInput.getElementsByTagName("TransitionValue")
        transitionList = []

        for i in range(TMsize*TMsize):
            transitionList.append(0)

        for i in transitions:
            position = i.getElementsByTagName('position')
            position = int(position[0].childNodes[0].data)
            source = i.getElementsByTagName('source')
            source = str(source[0].childNodes[0].data)
            index = i.getElementsByTagName('index')
            if source=='CODA':
                index = str(index[0].childNodes[0].data)
            else:
                if str(index[0].childNodes[0].data) == 'None':
                    index = None
                else: index = int(index[0].childNodes[0].data)
            dist = i.getElementsByTagName('distribution')
            dist = str(dist[0].childNodes[0].data)
            valueList = []
            values = i.getElementsByTagName('d')
            for i in values:
                try:
                    if source == 'CODA':
                        valueList.append(str(i.childNodes[0].data))
                    else: valueList.append(float(i.childNodes[0].data))
                except: pass
            if transitionList[position] == 0:
                if source == 'CODA':
                    transitionList[position] = TVgenerator_dict.TVgenerator(source, index, dist, valueList)
                else:
                    transitionList[position] = TVgenerator_dict.TVgenerator(source, index, dist, valueList)
            else:
                transitionList[position].update(TVgenerator_dict.TVgenerator(source, index, dist, valueList))
        
        return transitionList

