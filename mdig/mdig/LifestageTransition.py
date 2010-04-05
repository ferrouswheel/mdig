import time
import sys
import os
import logging
import re
import pdb
import xml.dom.minidom

import subprocess
from subprocess import Popen

import math
import numpy

from numpy import vstack, concatenate, random, array, loadtxt

import mdig
import GRASSInterface

class TVGenerator(list):
    """ Generates a transition value
    """
    def __init__(self, parameters, expressions, tm_size, index_values):
        self.tm_size = tm_size
        self.parameters = parameters
        self.expressions = expressions
        self.parameters_in_expressions = []
        self.log = logging.getLogger("mdig.tvgen")

        # Should we continue if an expression in the transition matrix tries to
        # divide by zero? Default: abort
        self.ignore_div_by_zero = False

        if not self.check_parameters(index_values):
            self.log.error("Parameters were not okay: exiting...")
            sys.exit(mdig.mdig_exit_codes['popmod'])
        
        self.map_pattern = re.compile(r'MAP_(\w*)', re.VERBOSE)
        for i in range(len(expressions)):
            # Parse the expressions

            # Sort parameter names by length so prefixes don't break longer names
            p_keys = parameters.keys()
            p_keys.sort(key=lambda x: -len(x))

            self.parameters_in_expressions.append({})
            # find all occurrences of parameter names
            for p in p_keys:
                if expressions[i].find(p) != -1:
                    self.parameters_in_expressions[i][p] = 1
            # search for MAP_* occurrences 
            #matches = self.map_pattern.findall(self.expressions[i])
            for m in self.map_pattern.finditer(self.expressions[i]):
                self.parameters_in_expressions[i][m.group()] = 1
            
        self.log.debug("Expressions for transitions matrix: [\n" + str(self) + " ]")
        #self.generate_default_parameter_map(index_values)

    def __str__(self):
        grid_string = ""
        for i in range(len(self.expressions)):
            # Code for printing out the matrix
            if i > 0 and i % self.tm_size == 0:
                grid_string += "\n"
            grid_string += "%s " % self.expressions[i]
        return grid_string

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
        """ This makes the parameter for unknown indices the same as the default
        """
        for i in range(len(self.expanded_expressions)):
            for par in self.parameters_in_expressions[i]:
                for index_value in index_values:
                    if not self.parameters[par].has_key(int(index_value)):
                        # There should be a default which we can map to
                        # since check_parameters shoudl have been called
                        self.parameters[par][int(index_value)] = \
                            self.parameters[par]["None"]

    def build_matrix(self, index_value, coords, pop_maps):
        tv_list=[]
	
        for i in range(len(self.expressions)):
            # arrange parameters so that longest get replaced first
            keys = self.parameters_in_expressions[i].keys()
            keys.sort(key=lambda x: -len(x))
            expanded_expression = self.expressions[i]
            for param_name in keys:
                if param_name[0:3] == "MAP":
                    ls_name = param_name[4:len(param_name)]
                    print "ls stage is " + ls_name
                    print "pop_maps keys " + str(pop_maps)
                    if ls_name in pop_maps:
                        expanded_expression = expanded_expression.replace(param_name, str(pop_maps[ls_name]))
                    else:
                        self.log.error("Couldn't find map %s for expression %s" % (ls_name, self.expressions[i]))
                else:
                    # check whether index_value exists for parameter
                    if index_value in self.parameters[param_name]:
                        expanded_expression = expanded_expression.replace(param_name, \
                             str(self.parameters[param_name][index_value].gen_val(index_value, coords)))
                    # protect against float based index maps when
                    # parameters use int
                    elif int(index_value) in self.parameters[param_name]:
			int_index = int(index_value)
                        expanded_expression = expanded_expression.replace(param_name, \
                             str(self.parameters[param_name][int_index].gen_val(int_index, coords)))
                    else:
                        expanded_expression = expanded_expression.replace(param_name, \
                             str(self.parameters[param_name]["None"].gen_val(index_value, coords)))
            try:
                expression_result = eval(expanded_expression)
                tv_list.append(expression_result)
            except ZeroDivisionError:
                self.log.error("ZeroDivisionError in expression" + \
                        ": %s" % expanded_expression)
                if not self.ignore_div_by_zero:
                    sys.exit()
                else:
                    tv_list.append(0.0)
            except NameError, e:
                self.log.error("%s in expression" + \
                        ": %s" % (str(e),expanded_expression))
                sys.exit()
        tm = array(tv_list)
        tm = tm.reshape(self.tm_size, self.tm_size)
        return tm

class ParamGenerator():
    """ Generator for parameters.

    @todo This really doesn't need to be a list

    Produces either static or random values,
    from source specified in xml file.
    """
    def __init__(self, source, index, dist, vals, model_dir):
        self.data = [0]
        self.source = source
        self.coda = None
        self.log = logging.getLogger("mdig.paramgen")
        print '%s   %s   %s   %s is parameter value source' %(source, index, dist, vals)
        try:
            if source == 'map':
                # TODO create a GRASSInterface command to load map to an array
                g = GRASSInterface.getG()
                self.map_name = str(vals[0])
                if (g.checkMap(self.map_name) != "raster"):
                    raise GRASSInterface.MapNotFoundException(self.map_name)
                map_range = g.getRange()
                n_rows = int(map_range[8][6:])
                n_cols = int(map_range[9][6:])
                cmd = "r.out.ascii -h input=" + self.map_name
                p = Popen(cmd, shell=True, stdout=subprocess.PIPE)
                map_ascii = p.communicate()[0]
                if map_ascii.find('*') != -1:
                    self.log.error("Null values in parameter map %s not allowed" % self.map_name) 
                    sys.exit(53)
                self.mat = numpy.matrix(map_ascii)
                self.mat = self.mat.reshape((n_rows,n_cols))
            elif source == 'CODA':
                self.coda = {}
                prefix = ""
                if not os.path.exists(index):
                    prefix = model_dir
                self.coda_index = \
                    loadtxt(os.path.join(prefix,index),converters={0: lambda x: 0.0})
                for i in range(len(vals)):
                    temp = loadtxt(os.path.join(prefix,vals[i]),converters={0: lambda x: 0.0})
                    if i == 0:
                        for j in range(len(self.coda_index[:,0])):
                            self.coda[j+1] = temp[int(self.coda_index[j,1])-1:int(self.coda_index[j,2]),1]
                    else:
                        for j in range(len(self.coda_index[:,0])):
                            self.coda[j+1] = concatenate((self.coda[j+1], \
                                temp[int(self.coda_index[j,1]-1):int(self.coda_index[j,2]), 1]))
            elif source == 'random':
                self.str = ("(%s.%s(%f,%f))" %(source, dist, vals[0], vals[1]))
#elif source == 'zero':
#break
            elif source == 'static':
                self.static = vals[0]
        except IOError:
            print '%s   %s   %s   %s parameter value source coding not valid' %(source, index, dist, vals)
            self.log.error("Are your CODA files okay?")
            sys.exit(849)

    def gen_val(self, index_value, coords):
        """Draws a random CODA iteration from the range specified in index for
           the corresponding parameter level
        """
        if self.source == 'CODA':
            if index_value in self.coda:
                return self.coda[index_value][random.random_integers(0,len(self.coda[index_value])-1)]
            elif int(index_value) in self.coda:
                return self.coda[int(index_value)][random.random_integers(0,len(self.coda[int(index_value)])-1)]
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
        self.model = model
        self.log = logging.getLogger("mdig.popmod")

        # Do lifestage transitions by individual rather than using
        # matrix multiplication. (SLOW!)
        self.by_individual = False

        # XML parsing
        self.xml_file = xml_file
        self.xml_dom = xml.dom.minidom.parse(xml_file)
        self.index_source = self.xml_to_index()

        # tm_size, used in defining/parsing 'expressions' list
        # same as number of lifestages
        self.tm_size = len(model.get_lifestage_ids())

        if model.base_dir:
            self.parameters = self.xml_to_param(model.base_dir)
        else:
            # This should only occur when loading files during model addition
            # to repository
            self.parameters = self.xml_to_param(os.path.dirname(self.xml_file))
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
        self.log.debug('Transition sources loaded.  Load time %f seconds'
                % load_time)
        self.log.debug('Transition matrix size set to %i x %i' % (self.tm_size, self.tm_size) )

        # Get the different indexes available
        index_values = GRASSInterface.getG().rasterValueFreq(self.index_source)
        index_values = [int(x[0]) for x in index_values]
        self.log.debug('Index values found were: ' + str(index_values))

        # Create matrix instance
        self.t_matrix = TVGenerator(self.parameters, self.expressions,
                self.tm_size, index_values)

    def apply_transition(self, ls_ids, current_pop_maps, destination_maps):
        #Timing of process
        start_time = time.time()

        ## Import Rasters
        # check Index raster name, check it exists
        index_raster = GRASSInterface.getG().getIndexRaster(self.index_source)
        # check list of rasters that comprise stages (in order)
        pop_raster_list = GRASSInterface.getG().getRasterList(current_pop_maps)

        self.log.debug("Converting stage rasters to ASCII...")
        ascii_pop_rasters = []
        ascii_out_rasters = []
        for i in pop_raster_list:
            # output to ascii, and also replace null values with 0
            data_fn, data_out_fn = GRASSInterface.getG().rasterToAscii(i,null_as_zero=True)
            ascii_pop_rasters.append(data_fn)
            ascii_out_rasters.append(data_out_fn)

        self.log.debug("Converting index file...")
        ascii_indexes = GRASSInterface.getG().indexToAscii(index_raster)

        # apply matrix multiplication
        self.process_rows(ls_ids, ascii_indexes, ascii_pop_rasters, ascii_out_rasters,
                destination_maps) 

        processingTime = time.time() - start_time
        print 'Transition matrix application completed. ' + \
            'Processing time %f seconds' % processingTime

    def process_rows(self, ls_ids, indexes, temp_rasters, temp_out_rasters, \
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
        f_in = open(indexes[0])
        fo_in_list.append(f_in)
        # 2nd (write) index file once opened erases contents of temp file
        f_out = open(indexes[1], 'w')
        fo_out_list.append(f_out)

        # add read and write file objects containing stage raster data
        for i in range(len(temp_rasters)):
            f_in = open(temp_rasters[i])
            fo_in_list.append(f_in)
            f_out = open(temp_out_rasters[i], 'w')
            fo_out_list.append(f_out)
    
        # Append array with raster data file objects from list        
        # .. for each row of the region
        for row in range(self.n_rows):
            # for each file
            for i in range(array_depth):
                temp_row = fo_in_list[i].readline().split()
                in_row_array[i] = temp_row

            # process individual cells
            # TODO: only works if an index map is specified - should
            # be able to work without one when it's all the same
            for j in range(in_row_array.shape[1]):
                #Calculate cell coordinates
                coords = (row,j)

                #Create and apply transition matrix instance            
                # in_row_array[0,j] because that's the index
                # in_row_array[1:,j] is data
                pop_maps = {}
                for l_i in range(0,len(ls_ids)):
                    pop_maps[ls_ids[l_i]] = in_row_array[l_i+1,j]
                    
                tm = self.t_matrix.build_matrix(in_row_array[0,j], coords, pop_maps)
                
                #print "cell contents: " + str(inRowArray[1:,j]) + str(type(inRowArray[1:,j]))
                #print "len(cell contents) = " +str(len(inRowArray[1:,j]))
                pop_cell = in_row_array[1:,j]
                #print "popCell.shape = " + str(popCell.shape)
                pop_cell = pop_cell.reshape((1, pop_cell.shape[0]))
                #print "popCell = " + str(popCell)
                
                # Long way to calculate transition, by individual behaviour
                if self.by_individual:
                    n_ls = pop_cell.shape[1]
                    out_cell = numpy.zeros(n_ls)
                    for ls_pop in range(0,n_ls):
                        if pop_cell[0,ls_pop] == 0: continue
                        norm_tm = tm[:,ls_pop]
                        sum_col = norm_tm.sum()
                        if sum_col > 1.0:
                            norm_tm = norm_tm / sum_col
                            # stochastically decide if decimal part of sum
                            # considered an individual
                            remainder = sum_col - int(sum_col)
                            if random.rand() < remainder:
                                sum_col = int(sum_col) + 1
                            else:
                                sum_col = int(sum_col)
                        else: sum_col = 1
                        x = random.rand(int(pop_cell[0,ls_pop] * sum_col))
                        threshold = 0; sum_so_far = 0
                        for ls_dest in range(0,n_ls):
                            threshold += norm_tm[ls_dest]
                            individuals = (x < threshold).sum()
                            out_cell[ls_dest] += individuals - sum_so_far
                            sum_so_far = individuals
                else:
                    out_cell = numpy.dot(tm,in_row_array[1:,j])
                #if out_cell2[0] != 0:
                    #import pdb; pdb.set_trace()
                if pop_cell[0,0] != 0:
                    print "T matrix: " + str(tm)
                    print "before: " + str(pop_cell)
                    print "after: " + str(out_cell)
                #print "outCell_1 = " + str(outCell)
                #print "outCell_shape = " + str(outCell.shape)
                out_row_array[0,j] = in_row_array[0,j]
                out_row_array[1:,j] = out_cell
                
            for i in range(array_depth): 
                if row == 0:
                    fo_out_list[i].writelines(self.header)
                self.write_lines_remove_zero(fo_out_list[i], out_row_array[i])

            
        for i in range(1,len(fo_out_list)):
            fo_out_list[i].close() # close temp out files
            fo_in_list[i].close() # close temp in files
            if i==0:
                pass # closes index file without re-writing it
            else: # re-write temp ascii files to rasters in GRASS workspace
                ascii_fn = temp_out_rasters[i-1]
                rast_name = out_pop_rasters[i-1]
                GRASSInterface.getG().importAsciiToRaster(ascii_fn,rast_name,0)
            # remove temporary ascii map files
            os.remove(temp_rasters[i-1])
            os.remove(temp_out_rasters[i-1])

    def write_lines_remove_zero(self,out_file,out_row):
        for val in out_row:
            if val == 0:
                out_file.write('* ')
            else:
                out_file.write(str(val) + " ")
        out_file.write("\n")

        #out_file.writelines(str(out_row_array[i]).strip(' []') \
                #+ '\n')

    def xml_to_index(self):
        x = self.xml_dom.getElementsByTagName("populationModule")[0]
        hab_source = x.getElementsByTagName("indexMap")
        index = str(hab_source[0].childNodes[0].data).strip()
        return index

    def xml_to_output_file(self):
        x = self.xml_dom.getElementsByTagName("populationModule")[0]
        output_file_source = x.getElementsByTagName("outputFile")
        output_file = str(output_file_source[0].childNodes[0].data).strip()
        return output_file

    def xml_to_param(self, model_dir):
        x = self.xml_dom.getElementsByTagName("populationModule")[0]
        parameters = x.getElementsByTagName("ParameterValue")
        param_dict = {}

        for i in parameters:
            parameter = str(i.getElementsByTagName('parameterName')[0].childNodes[0].data)
            parameter = parameter.strip()
            if parameter not in param_dict:
                param_dict[parameter] = {}
                
            source = str(i.getElementsByTagName('source')[0].childNodes[0].data)
            source = source.strip()
            index = i.getElementsByTagName('index')
            if source=='CODA':
                index = str(index[0].childNodes[0].data).strip()
            elif source=='map':
                # TODO check that index actually equals None in file
                index = 'None'
            else:
                if str(index[0].childNodes[0].data) == 'None':
                    index = 'None'
                else: index = int(index[0].childNodes[0].data)
            dist = i.getElementsByTagName('distribution')
            dist = str(dist[0].childNodes[0].data).strip()
            value_list = []
            values = i.getElementsByTagName('d')
            for v in values:
                try:
                    if source == 'CODA':
                        value_list.append(str(v.childNodes[0].data).strip())
                    if source == 'map':
                        value_list.append(str(v.childNodes[0].data).strip())
                    else:
                        value_list.append(float(v.childNodes[0].data.strip()))
                except:
                    pass
            if source == 'CODA':
                # Not actually None, but CODA deals with index within gen_val
                param_dict[parameter]["None"] = ParamGenerator(source, index, dist,
                    value_list, model_dir)
            else:
                param_dict[parameter][index] = ParamGenerator(source, index, dist,
                    value_list, model_dir)
            self.log.debug("Adding parameter " + parameter + " [index " +
                    str(index) + "]")
        return param_dict

    def xml_to_expression_list(self):
        x = self.xml_dom.getElementsByTagName("populationModule")[0]
        expressions = x.getElementsByTagName("expression")
        expression_list = [0]*(self.tm_size * self.tm_size)

        for i in expressions:
            position = i.getElementsByTagName('position')
            position = int(position[0].childNodes[0].data.strip())
            formula = i.getElementsByTagName('formula')
            formula = str(formula[0].childNodes[0].data).strip()
            
            if expression_list[position] == 0:
                expression_list[position] = formula
            else:
                self.log.warning("Expression for position " + str(position) + \
                        " already exists, overwriting...")
                expression_list[position] = formula
        
        return expression_list

    def get_coda_files_in_xml(self):
        x = self.xml_dom.getElementsByTagName("populationModule")[0]
        parameters = x.getElementsByTagName("ParameterValue")
        coda_files = []

        for i in parameters:
            source = str(i.getElementsByTagName('source')[0].childNodes[0].data)
            source = source.strip()
            index = i.getElementsByTagName('index')
            if source=='CODA':
                index = str(index[0].childNodes[0].data).strip()
                coda_files.append(index)
                values = i.getElementsByTagName('d')
                for v in values:
                    if len(v.childNodes) > 0:
                        coda_files.append(str(v.childNodes[0].data).strip())
        return coda_files

    def set_coda_files_in_xml(self, coda_files):
        x = self.xml_dom.getElementsByTagName("populationModule")[0]
        parameters = x.getElementsByTagName("ParameterValue")
        counter=0
        for i in parameters:
            source = str(i.getElementsByTagName('source')[0].childNodes[0].data)
            index = i.getElementsByTagName('index')
            if source=='CODA':
                index[0].childNodes[0].data = coda_files[counter]
                counter += 1
                values = i.getElementsByTagName('d')
                for v in values:
                    if len(v.childNodes) > 0:
                        v.childNodes[0].data = coda_files[counter]
                        counter += 1
        file_out = open(self.xml_file,'w')
        self.xml_dom.writexml(file_out)
        file_out.close()
