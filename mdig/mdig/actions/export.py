from mdig.actions.base import Action

import os
import sys
from subprocess import Popen, PIPE

from optparse import OptionParser

import mdig
from mdig import config
from mdig import grass


class ExportAction(Action):
    description = "Export images and movies of simulation."

    def __init__(self):
        super(ExportAction, self).__init__()
        self.parser = OptionParser(version=mdig.version_string,
                description=self.description,
                usage="%prog export [options] <model_name>")
        self.add_options()
        self.listeners = []
        self.float64 = False
        
    def add_options(self):
        Action.add_options(self)
        self.parser.add_option("-o","--overwrite",
                help="Overwrite existing files",
                action="store_true",
                dest="overwrite_flag")
        self.parser.add_option("-g","--gif",
                help="Output animated gif",
                action="store_true",
                dest="output_gif")
        self.parser.add_option("-i","--image",
                help="Output a series of images, one for each population distribution map",
                action="store_true",
                dest="output_image")
        self.parser.add_option("-m","--mappack",
                help="Output a zip file with exported maps",
                action="store_true",
                dest="output_map_pack")
        self.parser.add_option("-p","--rep",
                help="Output maps for rep instead of for occupancy envelope",
                action="append",
                type="int",
                dest="reps")
        self.parser.add_option("-l","--lifestage",
                help="Lifestage to analyse (lifestage name or default='all')",
                action="store",
                dest="output_lifestage",
                type="string")
        self.parser.add_option("-j","--instance",
                help="Export only instances specified (export all by default)",
                action="append",
                type="int",
                dest="instances")
        self.parser.add_option("-b","--background",
                help="Rast map to overlay pop. distributions on.",
                action="store",
                dest="background",
                type="string")
        self.parser.add_option("-x","--width",
                help="Set width of output image.",
                action="store",
                type="int",
                dest="width")
        self.parser.add_option("-y","--height",
                help="Set height of output image.",
                action="store",
                type="int",
                dest="height")
        self.parser.add_option("-d","--dir",
                help="Output dir to export to (default is model_mapset/mdig/output)",
                action="store",
                dest="outdir",
                type="string")

    def act_on_options(self,options):
        Action.act_on_options(self,options)
        c = config.get_config()
        c.overwrite_flag = self.options.overwrite_flag
        if self.options.output_lifestage is None:
            self.options.output_lifestage = "all"
        if self.options.width is None:
            self.options.width = c["OUTPUT"]["output_width"]
        if self.options.height is None:
            self.options.height = c["OUTPUT"]["output_height"]
        if self.options.background is None:
            self.options.background = c["OUTPUT"]["background_map"]
        if self.options.outdir is not None:
            if not os.path.isdir(self.options.outdir):
                sys.exit("No such output dir: %s" % self.options.outdir)
    
    def do_me(self,mdig_model):
        from mdig.instance import InvalidLifestageException, \
                InstanceIncompleteException, InvalidReplicateException, NoOccupancyEnvelopesException
        output_images = self.options.output_gif or self.options.output_image 
        if not (output_images or self.options.output_map_pack):
            self.log.error("No type for output was specified...")
            sys.exit("No type for output was specified...")
        # Get the instance objects that we are exporting
        if self.options.instances is None:
            # either all instances
            instances = mdig_model.get_instances()
        else:
            # or we convert instance indices to instance objects
            instances = []
            all_instances = mdig_model.get_instances()
            for i in self.options.instances:
                try:
                    instances.append(all_instances[i])
                except IndexError,e:
                    self.log.error("Bad instance index specified")
                    sys.exit("Bad instance index specified")
                except TypeError,e:
                    self.log.error("Bad instance index specified")
                    sys.exit("Bad instance index specified")

        show_output = config.get_config().output_level == "normal"
        for i in instances:
            try:
                if show_output:
                    if self.options.output_map_pack:
                        print "Creating map pack for instance %d" % i.get_index()
                    elif output_images:
                        print "Creating images for instance %d" % i.get_index()
                self.do_instance(i)
            except InvalidLifestageException, e:
                sys.exit(mdig.mdig_exit_codes["invalid_lifestage"])
            except InstanceIncompleteException, e:
                sys.exit(mdig.mdig_exit_codes["instance_incomplete"])
            except InvalidReplicateException, e:
                sys.exit(mdig.mdig_exit_codes["invalid_replicate_index"])
            except NoOccupancyEnvelopesException, e:
                sys.exit(mdig.mdig_exit_codes["missing_envelopes"])
            except Exception, e:
                import traceback
                print str(e)
                traceback.print_exc()
                sys.exit(mdig.mdig_exit_codes["unknown"])

    def check_lifestage(self,i,ls):
        if ls not in i.experiment.get_lifestage_ids():
            self.log.error("No such lifestage called %s in model." % str(ls))
            raise InvalidLifestageException()

    def check_background_map(self):
        g = grass.get_g()
        if self.options.background and not g.check_map(self.options.background):
            self.log.error("Couldn't find background map %s" % self.options.background)
            self.options.background = None
            #raise grass.MapNotFoundException(self.options.background)

    def do_rep(self,i,r):
        ls = self.options.output_lifestage
        map_list = []
        saved_maps = r.get_saved_maps(ls)
        model_name = i.experiment.get_name()

        # Normalise the color scale so that the lgend and range doesn't
        # keep changing for map to map
        self.log.info("Normalising colours")
        the_range = grass.get_g().normalise_map_colors(saved_maps.values())

        times = saved_maps.keys()
        times.sort(key=lambda x: float(x))
        output_images = self.options.output_gif or self.options.output_image 
        output_maps = self.options.output_map_pack
        if output_maps:
            rep_filenames = r.get_base_filenames(ls, output_dir=self.options.outdir) 
        elif output_images:
            rep_filenames = r.get_base_filenames(ls, extension='.png', output_dir=self.options.outdir) 
        for t in times:
            m = saved_maps[t]
            if output_images:
                map_list.append(self.create_frame(m, rep_filenames[t], model_name, t, ls, the_range))
                self.update_listeners(None, r, ls, t)
            elif output_maps:
                map_list.append(self.export_map(m, rep_filenames[t]))
                self.update_listeners_map_pack(None, r, ls, t)
        if self.options.output_gif:
            self.create_gif(map_list, r.get_base_filenames(ls, extension='_anim.gif',
                single_file=True, output_dir=self.options.outdir))
        elif output_maps:
            zip_fn = r.get_base_filenames(ls, extension='.zip', single_file=True,
                    output_dir=self.options.outdir)
            self.zip_maps(map_list, zip_fn)
        return map_list

    def do_instance(self,i):
        # TODO: only overwrite files if -o flag is set
        model_name = i.experiment.get_name()
        ls = self.options.output_lifestage
        self.check_lifestage(i, ls)
        all_maps = []

        output_images = self.options.output_gif or self.options.output_image 
        output_maps = self.options.output_map_pack

        # check that background map exists
        if output_images:
            self.check_background_map()

        if self.options.reps:
            if len(self.options.reps) > 1 and output_maps:
                    self.log.info("Exporting maps of reps: %s" % str(self.options.reps))
            # Run on replicates
            rs = i.replicates
            i.set_region()
            if len(rs) == 0:
                self.log.error("No replicates for instance %d. Have you run the model first?" \
                                % i.experiment.get_instances().index(i))
                raise InvalidReplicateException("No replicates available")
            for r_index in self.options.reps:
                if output_images:
                    self.log.info("Creating images for maps of rep %d" % r_index)
                elif output_maps:
                    self.log.info("Exporting maps of rep %d" % r_index)
                if r_index < 0 or r_index >= len(rs):
                    self.log.error("Invalid replicate index."
                            " Have you 'run' the model first or are you "
                            "specifying an invalid replicate index?")
                    if len(rs) > 0:
                        self.log.error("Valid replicate range is 0-%d." % (len(rs)-1))
                    raise InvalidReplicateException(r_index)
                r = rs[r_index]
                all_maps.extend(self.do_rep(i, r))
        else:
            if not i.is_complete():
                self.log.error("Instance " + repr(i) + " not complete")
                raise InstanceIncompleteException()
            i.change_mapset()
            # Run on occupancy envelopes
            if output_maps:
                self.log.info("Exporting occupancy envelope maps")
            elif output_images:
                self.log.info("Creating images for occupancy envelopes")
            self.log.debug("Fetching occupancy envelopes")
            env = i.get_occupancy_envelopes()
            if env is None:
                self.log.info("Couldn't find occupancy envelopes, so trying to generate...")
                i.update_occupancy_envelope()
                env = i.get_occupancy_envelopes()
                if env is None:
                    err_str = "Error creating occupancy envelopes."
                    self.log.error(err_str)
                    raise NoOccupancyEnvelopesException(err_str)
            map_list = []
            times = env[ls].keys()
            times.sort(key=lambda x: float(x))
            if output_maps:
                img_filenames = i.get_occ_envelope_img_filenames(ls, extension=False,dir=self.options.outdir) 
            elif output_images:
                img_filenames = i.get_occ_envelope_img_filenames(ls,dir=self.options.outdir) 
            for t in times:
                m = env[ls][t]
                if output_maps:
                    map_list.append(self.export_map(m,img_filenames[t],envelope=True))
                    self.update_listeners_map_pack(i, None, ls, t)
                elif output_images:
                    map_list.append(self.create_frame(m,img_filenames[t],model_name, t, ls))
                    if self.options.output_image:
                        self.log.info("Saved png to " + img_filenames[t])
                    self.update_listeners(i, None, ls, t)
            if self.options.output_gif:
                self.create_gif(map_list,
                        i.get_occ_envelope_img_filenames(ls, gif=True, dir=self.options.outdir) )
            elif output_maps:
                zip_fn = i.get_occ_envelope_img_filenames(ls, extension=False, gif=True, dir=self.options.outdir)[:-5]
                self.zip_maps(map_list, zip_fn)
            all_maps.extend(map_list)
        # If the user wanted an animated gif, then clean up the images
        # Also clean up exported ASCII maps outside of zip file
        if not self.options.output_image or output_maps:
            for m in all_maps:
                os.remove(m)

    def export_map(self, map, out_fn, envelope=False):
        old_region = "ExportActionBackupRegion"
        g = grass.get_g()
        g.run_command('g.region --o save=%s' % old_region)
        g.set_region(raster=map) 
        cmd = 'r.out.gdal input=%s output=%s.tif format=GTiff type=%s createopt="COMPRESS=PACKBITS,INTERLEAVE=PIXEL"'
        if envelope:
            if self.float64:
                cmd = cmd % (map, out_fn, 'Float64')
            else:
                cmd = cmd % (map, out_fn, 'Float32')
        else:
            cmd = cmd % (map, out_fn, 'UInt16')

        try:
            g.run_command(cmd)
            out_fn += ".tif"
        except grass.GRASSCommandException, e:
            # This swaps to 64 bit floats if GRASS complains about
            # losing precision on export.
            if "Precision loss" in e.stderr:
                self.float64 = True
                out_fn = self.export_map(map,out_fn,envelope)
            else:
                raise e
        finally:
            g.set_region(old_region) 
        return out_fn

    def zip_maps(self, maps, zip_fn):
        import zipfile
        if not zip_fn.endswith('.zip'):
            zip_fn += ".zip"
        if os.path.isfile(zip_fn) and not self.options.overwrite_flag:
            raise OSError("Zip file %s exists, use -o flag to overwrite" % zip_fn)
        try: 
            z = zipfile.ZipFile(zip_fn,mode='w',compression=zipfile.ZIP_DEFLATED)
        except RuntimeError:
            self.log.warning("No zlib available for compressing zip, " + \
                    "defaulting to plain storage")
            z = zipfile.ZipFile(zip_fn,mode='w')
        for m in maps:
            z.write(m, os.path.basename(m))
        z.close()
        self.log.info("Maps were stored in zip file %s" % zip_fn)

    def update_listeners(self,instance,replicate,ls,t):
        if instance:
            for l in self.listeners:
                if "export_image_complete" in dir(l):
                    l.export_image_complete(instance, None, ls,t)
        elif replicate:
            for l in self.listeners:
                if "export_image_complete" in dir(l):
                    l.export_image_complete(None, replicate, ls,t)

    def update_listeners_map_pack(self,instance,replicate,ls,t):
        if instance:
            for l in self.listeners:
                if "export_map_pack_complete" in dir(l):
                    l.export_map_pack_complete(instance, None, ls,t)
        elif replicate:
            for l in self.listeners:
                if "export_map_pack_complete" in dir(l):
                    l.export_map_pack_complete(None, replicate, ls,t)

    def create_gif(self,maps,fn):
        gif_fn = fn
        if os.path.isfile(gif_fn) and not self.options.overwrite_flag:
            raise OSError("Gif file %s exists, use -o flag to overwrite" % gif_fn)
        self.log.info("Creating animated gif with ImageMagick's convert utility.")
        output = Popen("convert -delay 100 " + " ".join(maps)
            + " " + gif_fn, shell=True, stdout=PIPE).communicate()[0]
        if len(output) > 0: self.log.debug("Convert output:" + output)
        self.log.info("Saved animated gif to " + gif_fn)
        return gif_fn

    def create_frame(self, map_name, output_name, model_name, year, ls, the_range = None):
        g = grass.get_g()
        if os.path.isfile(output_name) and not self.options.overwrite_flag:
            raise OSError("Gif file %s exists, use -o flag to overwrite" % output_name)
        g.set_output(filename = output_name, \
                width=self.options.width, height=self.options.height, display=None)
        g.run_command("d.erase")
        os.environ['GRASS_PNG_READ']="TRUE"

        # Check the background map exists
        if self.options.background:
            bg = self.options.background.split('@')
            if len(bg) > 1:
                map_ok = g.check_map(bg[0], bg[1])
            else:
                map_ok = g.check_map(bg)
            g.run_command("r.colors color=grey map=" + self.options.background)
            g.run_command("d.rast " + self.options.background)

        # This is code for setting the color table of each map manually
        # hasn't been easily integrated into interface, but easy for hacking
        # custom map output
        custom_color = False
        if custom_color:
            pcolor= Popen('r.colors map=%s rules=-' % map_name, \
                    shell=True, stdout=PIPE, stdin=PIPE)
            rule_string = "0%% %d:%d:%d\n" % (255,255,0)
            rule_string += "100%% %d:%d:%d\n" %  (255,255,0)
            rule_string += 'end'
            output = pcolor.communicate(rule_string)[0]
        ###
        # Draw the map
        g.run_command("d.rast " + map_name + " -o")
        # Draw the scale
        g.run_command("d.barscale tcolor=0:0:0 bcolor=none at=2,18 -l -t")
        # Code to enable/disable the legend
        do_legend = True
        if do_legend:
            if the_range:
                g.run_command("d.legend -s " + map_name + " range=%f,%f at=5,50,85,90" % the_range)
            else:
                g.run_command("d.legend -s " + map_name + " at=5,50,85,90")
        ###
        # Show the model name and year
        g.run_command("d.text at=2,90 size=3 text=" + model_name)
        g.run_command("d.text text=" + year + " at=2,93")
        # Save frame
        g.close_output()
        return output_name
