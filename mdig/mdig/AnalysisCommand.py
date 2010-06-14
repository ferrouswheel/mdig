import re
import logging
import os
import random
import pdb

import mdig

import OutputFormats
import MDiGConfig

class AnalysisCommand:
    """ Wraps a command line string and associated utilities to be run on
        multiple maps.

    >>> ac = AnalysisCommand("testing %1 %2")
    >>> ac.get_earliest_time()
    2
    """

    def __init__ (self, cmd_string):
        """ Initialise the analysis command

        >>> ac = AnalysisCommand("testing")
        >>> ac.cmd_string
        'testing'
        >>> ac.start_time
        0
        >>> ac.output_fn
        """
        self.cmd_string = cmd_string
        self.start_time = 0
        self.earliest_time = None
        self.times = None
        self.output_fn = None
        self.output_fn_base = None
        self.log = logging.getLogger("mdig.AnalysisCommand")

    def get_earliest_time(self):
        if self.earliest_time is None:
            # Find earliest map in cmd_string (represented by %\d)
            # Allow escaping of % with double... e.g. %%1 doesn't match
            map_matches = re.findall('(?<!%)%\d+',self.cmd_string)
            if len(map_matches) == 0:
                self.earliest_time = 0
                self.log.warn(
                    "No map references in command, will run command for " +
                    "every map, but it won't be specific to the map.")
            for map_d in map_matches:
                map_index = int(map_d[1:])
                if map_index > self.earliest_time:
                    self.earliest_time = map_index
            self.log.info(
                    "Earliest map in cmd_string is %d before present" % self.earliest_time)
        return self.earliest_time

    def get_output_filename_base(self):
        if self.output_fn_base is None:
            mdig_config = MDiGConfig.get_config()
            if mdig_config.analysis_filename_base is None:
                #create random name
                self.output_fn_base = \
                        repr(os.getpid()) + "_" + repr(int(random.random()*1000000)) \
                        + ".dat"
            else:
                self.output_fn_base = mdig_config.analysis_filename_base
        return self.output_fn_base

    def init_output_file(self, instance, rep=None):
        """ Initialise a new output file """
        mdig_config = MDiGConfig.get_config()
        tmp_fn = self.get_output_filename_base()
        #   append variable/ls/region info
        if rep:
            tmp_fn = OutputFormats.create_filename(instance) + "_" + \
                     repr(instance.replicates.index(rep)) + "_" + tmp_fn
        else:
            tmp_fn = OutputFormats.create_filename(instance) + "_" + tmp_fn
        
        # check if file exists
        if os.path.isfile(tmp_fn):
            if mdig_config.overwrite_flag:
                self.log.warning("Analysis output file " +tmp_fn+ " exists, overwriting...")
                os.remove(tmp_fn)
            else:
                self.log.error("Analysis output file exists")
                raise mdig.OutputFileExistsException(tmp_fn)
        self.log.info("Analysis output file set to " + tmp_fn + " (path " +
                os.getcwd() + ")")
        self.output_fn = tmp_fn
        return tmp_fn

    def insert_output_into_cmd(self):
        """
        replace %f with analysis_filename_base (or generated name)
        if it exists in cmd_string, otherwise add output redirection
        to command string
        """
        if self.output_fn is None:
            raise OutputFileNotSetException()
        tmp_cmd_string = self.cmd_string
        tmp_fn = self.output_fn
        if re.search("(?<!%)%f",tmp_cmd_string) is not None:
            # do reg ex replace
            tmp_cmd_string = re.sub("%f", tmp_fn, tmp_cmd_string)
        else:
            # otherwise add output redirection >> to cmd_string
            tmp_cmd_string += (" >> %s" % tmp_fn)
        return tmp_cmd_string

    def run_command(self,maps):
        if self.times is None:
            raise Exception("Times to run command on not set")
        # replace %f 
        tmp_cmd_string = self.insert_output_into_cmd()
        # Skip ahead to the first time that has enough past maps to
        # satisfy the command line.
        for t in self.times[self.get_earliest_time():]:
            ret = self.run_command_once(t,maps,tmp_cmd_string)
            if ret is not None:
                self.log.error("Analysis command did not return 0")
    
    def run_command_once(self,t,maps,cmd_string):
        # replace %t with current time if it exists in cmd_string
        tmp_cmd_string = re.sub("%t", repr(t), cmd_string)
        
        # Replace %(number) references with the map names
        # ...Allow escaping of % with double... e.g. %%1 doesn't match
        map_matches = re.findall('(?<!%)%\d',tmp_cmd_string)
        for map_d in map_matches:
            map_index = int(map_d[1:])
            t_index = self.times.index(t)
            if t_index - map_index < 0:
                raise IndexError("at time index %d but command as reference to map %s time steps earlier than current" % (t_index,map_index) )
            tmp_cmd_string = re.sub("%" + repr(map_index),
                    maps[repr(self.times[t_index - map_index])], tmp_cmd_string)
        
        # Add time to the output file if option is enabled.
        mdig_config = MDiGConfig.get_config()
        if mdig_config.analysis_print_time:
            file = open(self.output_fn,'a')
            file.write('%d ' % t)
            file.close()
        
        # Run command on maps
        self.log.info("Running analysis command: " + tmp_cmd_string )
        cmd_stdout = os.popen(tmp_cmd_string,"r")
        stdout = cmd_stdout.read()
        ret = cmd_stdout.close()
        return ret

    def set_times(self, period, o_times, times=None):
        """ Check a list of the times against the actual stored timesteps and
            also set the time the command will run on.

        @param period that times need to remain in to be valid
        @param o_times the original list of stored/saved map times.
        @param times a list of times to run command on, -ve values are interpreted
        as indices from the end of the array e.g. -1 == last map.
        @return times with -ve indices replaced and all times checked that they
        exist
        """
        # sort just in case
        o_times = list(o_times)
        o_times.sort()
        if times is None:
            # if no time is user-specified, use all existing times,
            times = o_times
        else:
            #check times
            for t in times:
                if t < 0:
                    # If negative value, then use as index
                    times[times.index(t)] = o_times[t]
                elif t < period[0] or t > period[1]:
                    raise ValueError("Time outside simulation range: %d" % t)
                elif t not in o_times:
                    raise ValueError("Time not in saved maps: %d" % t)
            times.sort()
        # check that there are enough maps to satisfy the command line
        # at least once.
        if times[0] - self.get_earliest_time() < o_times[0]:
            self.log.error("Not enough past maps to fulfill "
                    "command line with earliest map %d maps "
                    "before present" % self.get_earliest_time())
            raise mdig.NotEnoughHistoryException()
        self.times = times
        return times

class OutputFileNotSetException(Exception): pass

