import time
import sys
import os
import logging
import re
import xml.dom.minidom

import subprocess
from subprocess import Popen

from scipy.io import read_array

import numpy
from numpy import vstack, concatenate, random, array

import mdig
import GRASSInterface

class TVGenerator(list):
    """ Generates a transition value
    """
    def __init__(self, parameters, expressions, tm_size, index_values):
        self.tm_size = tm_size
        self.parameters = parameters
        self.expressions = expressions
        self.expanded_expressions = []
        self.parameters_in_expressions = []
        self.log = logging.getLogger("mdig.tvgen")

        if not self.check_parameters(index_values):
            self.log.error("Parameters were not okay: exiting...")
            sys.exit(mdig.mdig_exit_codes['popmod'])

        # TODO replace the below regex with a more generic and smaller one
        pattern = re.compile(r'''
                       #Don't specify matching beginning of string (no ^)
        \s*            #matches any number of whitespaces         
        (\w*)          #matches any number (0+) of alphanumeric characters (parameter name)
        \s*            #matches any number of whitespaces         
        ([/+/-/*//]?)  #Match any mathematical operators (optional)
        \s*            #matches any number of whitespaces         
        (\w*)          #matches any number (0+) of alphanumeric characters (parameter name)
        \s*            #matches any number of whitespaces         
        ([/+/-/*//]?)  #Match any mathematical operators (optional)
        \s*            #matches any number of whitespaces         
        (\w*)          #matches any number (0+) of alphanumeric characters (parameter name)
        \s*            #matches any number of whitespaces         
        ([/+/-/*//]?)  #Match any mathematical operators (optional)
        \s*            #matches any number of whitespaces         
        (\w*)          #matches any number (0+) of alphanumeric characters (parameter name)
        \s*            #matches any number of whitespaces         
        ([/+/-/*//]?)  #Match any mathematical operators (optional)
        \s*            #matches any number of whitespaces         
        (\w*)          #matches any number (0+) of alphanumeric characters (parameter name)
        \s*            #matches any number of whitespaces         
        ([/+/-/*//]?)  #Match any mathematical operators (optional)
        \s*            #matches any number of whitespaces         
        (\w*)          #matches any number (0+) of alphanumeric characters (parameter name)
        \s*            #matches any number of whitespaces         
        ([/+/-/*//]?)  #Match any mathematical operators (optional)
        \s*            #matches any number of whitespaces         
        (\w*)          #matches any number (0+) of alphanumeric characters (parameter name)
                ''', re.VERBOSE)
        for i in range(len(expressions)):
            print expressions[i]
            self.parameters_in_expressions.append([])
            expression_temp = pattern.search(expressions[i]).groups()
            temp_exp_list = []
            go_between_list = []

            #remove blank groups from parsing, move expression elements to a
            # list (tempExpList)
            for j in expression_temp:
                if j !='':
                    temp_exp_list.append(j)
                    
            for g in temp_exp_list:
                #if expression element is a parameter, add 'gen_val' syntax
                if parameters.has_key(g):
                    self.parameters_in_expressions[i].append(g)
                    temp_string = "self.parameters['%s'][%s].gen_val(%s, coords)" % \
                        (g, "%(index_value)i", "%(index_value)i")
                    go_between_list.append(temp_string)
                else:
                    go_between_list.append(g)
                    
            # combines elements of tempExpList into a single string and adds them
            # to the expressionList
            self.expanded_expressions.append(''.join(go_between_list))
        self.generate_default_parameter_map(index_values)

    def check_parameters(self, index_values):
        is_okay = True
        for p in self.parameters:
            p_val = self.parameters[p]
            if p_val.has_key("None"):
                # This parameter has a default generator regardless of index
                continue
            for i in index_values:
                # check that the parameter has a generator for each possible
                # index
                if not p_val.has_key(i):
                    self.log.error("Parameter %s does not have a generator " \
                    "for index %s (or a default)" % (str(p),str(i)))
                    is_okay = False
        return is_okay

    def generate_default_parameter_map(self, index_values):
        for i in range(len(self.expanded_expressions)):
            for par in self.parameters_in_expressions[i]:
                for index_value in index_values:
                    if not self.parameters[par].has_key(int(index_value)):
                        # There should be a default which we can map to
                        # since check_parameters shoudl have been called
                        self.parameters[par][int(index_value)] = \
                            self.parameters[par]["None"]

    def build_matrix(self, index_value, coords):
        tv_list = []
        for i in range(len(self.expanded_expressions)):
            t_val = self.expanded_expressions[i] % vars()
            tv_list.append(eval(t_val))
        tm = array(tv_list)
        tm = tm.reshape(self.tm_size, self.tm_size)
        return tm

class ParamGenerator():
    """ Generator for parameters.

    @todo This really doesn't need to be a list

    Produces either static or random values,
    from source specified in xml file.
    """
    def __init__(self, source, index, dist, vals):
        self.data = [0]
        self.source = source
        self.coda = None
        print '%s   %s   %s   %s is parameter value source' %(source, index, dist, vals)
        try:
            if source == 'map':
                # TODO create a GRASSInterface command to load map to an array
                g = GRASSInterface.getG()
                self.map_name = str(vals[0])
                if (g.checkMap(self.map_name) != "raster"):
                    raise GRASSInterface.MapNotFoundException()
                map_range = g.getRange()
                n_rows = int(map_range[8][6:])
                n_cols = int(map_range[9][6:])
                cmd = "r.out.ascii -h input=" + self.map_name
                p = Popen(cmd, shell=True, stdout=subprocess.PIPE)
                self.mat = numpy.matrix(p.communicate()[0])
                self.mat = self.mat.reshape((n_rows,n_cols))
            elif source == 'CODA':
                self.coda = []
                self.coda.append(read_array(index))
                for i in range(len(vals)):
                    temp = read_array(vals[i])
                    if i == 0:
                        for j in range(len(self.coda[0])):
                            self.coda.append(temp[int(self.coda[0][j,1])-1:int(self.coda[0][j,2]),1])
                    else:
                        for j in range(len(self.coda[0])):
                            self.coda[j+1] = concatenate((self.coda[j+1], \
                                temp[int(self.coda[0][j,1]-1):int(self.coda[0][j,2]), 1]))
            elif source == 'random':
                self.str = ("(%s.%s(%f,%f))" %(source, dist, vals[0], vals[1]))
#elif source == 'zero':
#break
            elif source == 'static':
                self.static = vals[0]
        except IOError:
            print '%s   %s   %s   %s parameter value source coding not valid' %(source, index, dist, vals)

    def gen_val(self, index_value, coords):
        """Draws a random CODA iteration from the range specified in index for
           the corresponding parameter level
        """
        if self.source == 'CODA':
           return self.coda[index_value][random.random_integers(0,len(self.coda[index_value]))]
        elif self.source == 'random':
           return eval(self.str)
        elif self.source == 'zero':
           return 0
        elif self.source == 'static':
           return self.static
        elif self.source == 'map':
           return self.mat[coords[0], coords[1]]

class LifestageTransition:

    def __init__(self,xml_file, model):
        # Init timing of load process
        start_time = time.time()

#self.m_instance = model_instance 
        self.log = logging.getLogger("mdig.popmod")

        # XML parsing
        self.xml_dom = xml.dom.minidom.parse(xml_file)
        self.index_source = self.xml_to_index()

        # tm_size, used in defining/parsing 'expressions' list
        # same as number of lifestages
        self.tm_size = len(model.get_lifestage_ids())

        self.parameters = self.xml_to_param()
        self.expressions = self.xml_to_expression_list()

        # determine size of rasters
        self.range_data = GRASSInterface.getG().getRange()
        # process range_data
        self.n_rows = int(self.range_data[8][6:])
        self.n_cols = int(self.range_data[9][6:])
        self.header = str(self.range_data[2] + self.range_data[3] + self.range_data[4] +
                self.range_data[5] + self.range_data[8] + self.range_data[9])

        # End timing of load process
        load_time = time.time() - start_time
        self.log.debug('Transition matrix set to %i x %i' % (self.tm_size, self.tm_size) )
        self.log.debug('Transition sources loaded.  Load time %f seconds'
                % load_time)

        # Get the different indexes available
        index_values = GRASSInterface.getG().rasterValueFreq(self.index_source)
        index_values = [int(x[0]) for x in index_values]
        
        # Create matrix instance
        self.t_matrix = TVGenerator(self.parameters, self.expressions,
                self.tm_size, index_values)

    def apply_transition(self, current_pop_maps, destination_maps):
        #Timing of process
        start_time = time.time()

        ## Import Rasters
        # check Index raster name, check it exists
        index_raster = GRASSInterface.getG().getIndexRaster(self.index_source)
        # check list of rasters that comprise stages (in order)
        pop_raster_list = GRASSInterface.getG().getRasterList(current_pop_maps)

        # create list of temp output raster names
        #output_raster_list = []
        #for i in popRasterList:
        #    outputRasterList.append(str(i) + "_1")
        # ^ replaced by passed destination_maps

        # convert GRASS rasters to temp ASCII files
        print "Converting stage rasters to ASCII..."
        ascii_pop_rasters = []
        ascii_out_rasters = []
        for i in pop_raster_list:
            # output to ascii, and also replace null values with 0
            data_fn, data_out_fn = GRASSInterface.getG().rasterToAscii(i,null_as_zero=True)
            ascii_pop_rasters.append(data_fn)
            ascii_out_rasters.append(data_out_fn)

        print "Converting index file..."
        ascii_indexes = GRASSInterface.getG().indexToAscii(index_raster)

        # apply matrix multiplication
        self.process_rows(ascii_indexes, ascii_pop_rasters, ascii_out_rasters,
                destination_maps) 

        processingTime = time.time() - start_time
        print 'Transition matrix application completed. ' + \
            'Processing time %f seconds' % processingTime

    def process_rows(self, indexes, temp_rasters, temp_out_rasters, \
            out_pop_rasters):
        """ Applies an instance of the transition matrix to the population 
        rasters and outputs new rasters to the current GRASS workspace.

        @todo This should eventually be externalised into a C module that
        directly reads the GRASS maps, but for now we convert to/from and
        process ASCII maps.
        """
        numpy.set_printoptions(linewidth=200)
        array_depth = len(temp_rasters) + 1

        # create empty array for storing current row data
        in_row_array = numpy.zeros((array_depth, self.n_cols))
        out_row_array = numpy.zeros((array_depth, self.n_cols))

        # Create empty lists to hold file objects (current row data is read
        # from these file objects
        fo_in_list = []
        fo_out_list = []

        # add readable file object containing index data
        f_in = open(indexes[0][1])
        fo_in_list.append(f_in)
        # 2nd (write) index file once opened erases contents of temp file
        f_out = open(indexes[1][1], 'w')
        fo_out_list.append(f_out)

        # add read and write file objects containing stage raster data
        for i in range(len(temp_rasters)):
            f_in = open(temp_rasters[i][1])
            fo_in_list.append(f_in)
            f_out = open(temp_out_rasters[i][1], 'w')
            fo_out_list.append(f_out)
    
        # Append array with raster data file objects from list        
        # .. for each row of the region
        for row in range(self.n_rows):
            # for each file
            for i in range(array_depth):
                temp_row = fo_in_list[i].readline().split()
                in_row_array[i] = temp_row

            # process individual cells
            # TODO only works if an index map is specified!
            for j in range(in_row_array.shape[1]):
                #Calculate cell coordinates
                #E = int(rangeData[4][6:])+(j*float(rangeData[7][6:]))
                #N = int(rangeData[3][6:])+(int(rangeData[2][6:])-row)*float(rangeData[6][6:])
                coords = (row,j)

                #Create and apply transition matrix instance            
                tm = self.t_matrix.build_matrix(in_row_array[0,j], coords)
                
                #print "T matrix: " + str(MatrixInstance)
                #print "cell contents: " + str(inRowArray[1:,j]) + str(type(inRowArray[1:,j]))
                #print "len(cell contents) = " +str(len(inRowArray[1:,j]))
                pop_cell = in_row_array[1:,j]
                #print "popCell.shape = " + str(popCell.shape)
                pop_cell = pop_cell.reshape((1, pop_cell.shape[0]))
                #print "popCell = " + str(popCell)
                out_cell = numpy.dot(tm,in_row_array[1:,j])
                #print "outCell_1 = " + str(outCell)
                #print "outCell_shape = " + str(outCell.shape)
                out_row_array[0,j] = in_row_array[0,j]
                out_row_array[1:,j] = out_cell
                
            for i in range(array_depth): 
                if row == 0:
                    fo_out_list[i].writelines(self.header)
                fo_out_list[i].writelines(str(out_row_array[i]).strip(' []') \
                        + '\n')
            
        for i in range(1,len(fo_out_list)):
            fo_out_list[i].close() # close temp out files
            if i==0:
                pass # closes index file without re-writing it
            else: # re-write temp ascii files to rasters in GRASS workspace
                ascii_fn = temp_out_rasters[i-1][1]
                rast_name = out_pop_rasters[i-1]
                GRASSInterface.getG().importAsciiToRaster(ascii_fn,rast_name)

    def xml_to_initial_state(self):
        raster_maps = self.xml_dom.getElementsByTagName("raster")
        #print rasterMaps.childNodes[0].data
        initial_state_maps = []
        try:
            for i in raster_maps:
                initial_state_maps.append(str(i.childNodes[0].data))
        except IndexError:
            print "Index Error - Blank initial_state raster specification " + \
                "in XML file?"         
        return initial_state_maps

    def xml_to_index(self):
        x = self.xml_dom.firstChild
        hab_source = x.getElementsByTagName("indexMap")
        index = str(hab_source[0].childNodes[0].data)
        return index

    def xml_to_output_file(self):
        x = self.xml_dom.firstChild
        output_file_source = x.getElementsByTagName("outputFile")
        output_file = str(output_file_source[0].childNodes[0].data)
        return output_file

    def xml_to_param(self):
        x = self.xml_dom.firstChild
        parameters = x.getElementsByTagName("ParameterValue")
        param_dict = {}

        for i in parameters:
            parameter = str(i.getElementsByTagName('parameterName')[0].childNodes[0].data)
            if parameter not in param_dict:
                param_dict[parameter] = {}
                
            source = str(i.getElementsByTagName('source')[0].childNodes[0].data)
            index = i.getElementsByTagName('index')
            if source=='CODA':
                index = str(index[0].childNodes[0].data)
            elif source=='map':
                # TODO check that index actually equals None in file
                index = 'None'
            else:
                if str(index[0].childNodes[0].data) == 'None':
                    index = 'None'
                else: index = int(index[0].childNodes[0].data)
            dist = i.getElementsByTagName('distribution')
            dist = str(dist[0].childNodes[0].data)
            value_list = []
            values = i.getElementsByTagName('d')
            for v in values:
                try:
                    if source == 'CODA':
                        value_list.append(str(v.childNodes[0].data))
                    if source == 'map':
                        value_list.append(str(v.childNodes[0].data))
                    else: value_list.append(float(v.childNodes[0].data))
                except: pass
            param_dict[parameter][index] = ParamGenerator(source, index, dist,
                    value_list)
            self.log.debug("Adding parameter " + parameter + " [index " +
                    str(index) + "]")
        return param_dict

    def xml_to_expression_list(self):
        x = self.xml_dom.firstChild
        expressions = x.getElementsByTagName("expression")
        expression_list = [0]*(self.tm_size * self.tm_size)

        for i in expressions:
            position = i.getElementsByTagName('position')
            position = int(position[0].childNodes[0].data)
            formula = i.getElementsByTagName('formula')
            formula = str(formula[0].childNodes[0].data)
            
            if expression_list[position] == 0:
                expression_list[position] = formula
            else:
                self.log.warning("Expression for position " + position + \
                        "already exists, overwriting...")
                expression_list[position].update(formula)
        
        return expression_list

    #Old transition reading from xml file
    # ASK: to delete?
    #def xml_to_transition_list(self):
        #x = self.xml_dom.firstChild
        #transitions = x.getElementsByTagName("TransitionValue")
        #transition_list = []
        #for i in range(self.tm_size*self.tm_size):
            #transition_list.append(0)

        #for i in transitions:
            #position = i.getElementsByTagName('position')
            #position = int(position[0].childNodes[0].data)
            #source = i.getElementsByTagName('source')
            #source = str(source[0].childNodes[0].data)
            #index = i.getElementsByTagName('index')
            #if source=='CODA':
                #index = str(index[0].childNodes[0].data)
            #else:
                #if str(index[0].childNodes[0].data) == 'None':
                    #index = None
                #else: index = int(index[0].childNodes[0].data)
            #dist = i.getElementsByTagName('distribution')
            #dist = str(dist[0].childNodes[0].data)
            #value_list = []
            #values = i.getElementsByTagName('d')
            #for i in values:
                #try:
                    #if source == 'CODA':
                        #value_list.append(str(i.childNodes[0].data))
                    #else:
                        #value_list.append(float(i.childNodes[0].data))
                #except:
                    #pass
            #if transition_list[position] == 0:
                ## ASK: This used to initialise TVgenerator_dict
                #if source == 'CODA':
                    #transition_list[position] = TVGenerator(source, index, dist,
                            #value_list)
                #else:
                    #transition_list[position] = TVGenerator(source, index, dist,
                            #value_list)
            #else:
                #transition_list[position].update(TVGenerator(source, index, dist,
                            #value_list))
        
        #return transition_list

