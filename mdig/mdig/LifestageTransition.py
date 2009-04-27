import time
import re
import xml.dom.minidom
from scipy.io import read_array
from numpy import vstack, concatenate, random, array

import GRASSInterface

class TVGenerator(list):
    """ Generates a transition matrix?

    ASK What does TV stand for?
    """
    def __init__(self, parameters, expressions, tm_size):
        self.tm_size = tm_size
        self.parameters = parameters
        expression_list = []
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
        for i in expressions:               
            expression_temp = pattern.search(i).groups()
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
                    temp_string = "self.parameters['%s'].gen_val(%s, coords)" % (g, "%(indexValue)i")
                    go_between_list.append(temp_string)
                else:
                    go_between_list.append(g)
                    
            # combines elements of tempExpList into a single string and adds them
            # to the expressionList
            self.append(''.join(go_between_list))

    def build_matrix(self, index_value, coords):
        tv_list = []
        for i in range(len(self)):
            t_val = self[i] % vars()
            tv_list.append(eval(t_val))
        tm = array(tv_list)
        tm = tm.reshape(self.tm_size, self.tm_size)
        return tm 

class ParamGenerator(list):
    """ Generator for parameters.

    Produces either static or random values,
    from source specified in xml file.
    """
    def __init__(self, source, index, dist, vals):
        self.data = [0]
        self.source = source
        try:
            if source == 'map':
                # TODO create a GRASSInterface command to load map to an array
                self.map_name = str(vals[0])
                map_range = rasterIO_2.get_range()
                n_rows = int(map_range[8][6:])
                n_cols = int(map_range[9][6:])
                cmd = "r.out.ascii -h input=%s" %(self.map_name)
                p = grass.pipe_command(cmd)
                self.mat = numpy.matrix(p.communicate()[0])
                self.mat = self.mat.reshape((n_rows,n_cols))
            if source == 'CODA':
                self.append(read_array(index))
                for i in range(len(vals)):
                    temp = read_array(vals[i])
                    # ASK: The two cases below are the same?
                    if i == 0:
                        for j in range(len(self[0])):
                            self.append(temp[int(self[0][j,1])-1:int(self[0][j,2]),1])
                    else:
                        for j in range(len(self[0])):
                            self[j+1] = concatenate((self[j+1], \
                                temp[int(self[0][j,1]-1):int(self[0][j,2]), 1]))
            if source == 'random':
                self.str = ("(%s.%s(%f,%f))" %(source, dist, vals[0], vals[1]))
            if source == 'zero':
                pass
            if source == 'static':
                self.static = vals[0]
        except IOError:
            print '%s   %s   %s   %s parameter value source coding not valid' %(source, index, dist, vals)

    def gen_val(self, index_value, coords):
        """Draws a random CODA iteration from the range specified in index for the corresponding parameter level"""
        if self.source == 'CODA':
           return self[index_value][random.random_integers(0,len(self[index_value]))]
        elif self.source == 'random':
           return eval(self.str)
        elif self.source == 'zero':
           return 0
        elif self.source == 'static':
           return self.static
        elif self.source == 'map':
           return self.mat[coords[0], coords[1]]

class LifestageTransition:

    def __init__(self,xml_file, model_instance):
        # Init timing of load process
        self.start_time = time.time()

        self.m_instance = model_instance 
        self.log = logging.getLogger("mdig.popmod")

        # XML parsing
        self.xml_dom = xml.dom.minidom.parse(xml_file)
        self.index_source = self.xml_to_index()

        # tm_size, used in defining/parsing 'expressions' list
        # same as number of lifestages
        self.tm_size = len(model_instance.exp.getLifestageIDs())

        self.parameters = self.xml_to_param()
        self.expressions = self.xml_to_expression_list(tm_size)

        # determine size of rasters
        self.range_data = GRASSInterface.getG().getRange()
        # process range_data
        n_rows = int(self.range_data[8][6:])
        n_cols = int(self.range_data[9][6:])
        header = str(self.range_data[2] + self.range_data[3] + self.range_data[4] +
                self.range_data[5] + self.range_data[8] + self.range_data[9])

        # End timing of load process
        load_time = time.time() - start_time
        self.log.debug('Transition matrix set to %i x %i' % (tm_size, tm_size) )
        self.log.debug('Transition sources loaded.  Load time %f seconds'
                % load_time)

        # Create matrix instance
        self.t_matrix = TVGenerator(parameters, expressions, tm_size)

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
            data_fn, data_out_fn = GRASSInterface.getG().rasterToAscii(i)
            ascii_pop_rasters.append(data_fn)
            ascii_out_rasters.append(data_out_fn)

        print "Converting index file..."
        ascii_indexes = GRASSInterface.getG().indexToAscii(index_raster)

        # apply matrix multiplication
        process_rows(ascii_indexes, ascii_pop_rasters, ascii_out_rasters) 

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
            fo_list.append(f_in)
            f_out = open(temp_out_rasters[i][1])
            fo_out_list.append(f_out)
    
        # Append array with raster data file objects from list        
        # .. for each row of the region
        for row in range(self.n_rows): 
            # for each file
            for i in range(array_depth):
                in_row_array[i] = fo_in_list[i].readline().split()

            # process individual cells
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
            
        for i in range(len(fo_out_list)):
            fo_out_list[i].close() # close temp out files
            if i==0:
                pass # closes index file without re-writing it
            else: # re-write temp ascii files to rasters in GRASS workspace
                rast_name = output_pop_rasters[i-1]
                temp_to_rast_cmd = "r.in.ascii input=%s output=%s" % \
                    (temp_out_rasters[i-1][1], rast_name)
                GRASSInterface.getG().run_command(temp_to_rast_cmd)

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
            if i == parameters[0]:
                if source == 'CODA':
                    param_dict[parameter] = ParamGenerator(source, index, dist,
                            value_list)
                else:
                    param_dict[parameter] = ParamGenerator(source, index, dist,
                            value_list)
            else:
                param_dict[parameter]=(ParamGenerator(source, index, dist,
                            value_list))
        
        return param_dict

    def xml_to_expression_list(self):
        x = xml_dom.firstChild
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
                expression_list[position].update(formula)
        
        return expression_list

    #Old transition reading from xml file
    # ASK: to delete?
    def xml_to_transition_list(self):
        x = self.xml_dom.firstChild
        transitions = x.getElementsByTagName("TransitionValue")
        transition_list = [0]*(self.tm_size*self.tm_size):

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
            value_list = []
            values = i.getElementsByTagName('d')
            for i in values:
                try:
                    if source == 'CODA':
                        value_list.append(str(i.childNodes[0].data))
                    else:
                        value_list.append(float(i.childNodes[0].data))
                except:
                    pass
            if transition_list[position] == 0:
                # ASK: This used to initialise TVgenerator_dict
                if source == 'CODA':
                    transition_list[position] = TVGenerator(source, index, dist,
                            value_list)
                else:
                    transition_list[position] = TVGenerator(source, index, dist,
                            value_list)
            else:
                transition_list[position].update(TVGenerator(source, index, dist,
                            value_list))
        
        return transition_list

