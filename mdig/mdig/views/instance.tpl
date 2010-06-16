<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>MDiG - {{instance.experiment.get_name()}} - Instance {{idx}} </title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
%include css
</head>
<body>
<small><a href="/models/">All models</a></small>
%include status_headline task_updates=task_updates, task_order=task_order
<h1><a href="/models/{{instance.experiment.get_name()}}">{{instance.experiment.get_name()}}</a> - Instance {{idx}}</h1>
%if error:
<div class="error">
Error: {{error}}
</div>
%end
<div class="details">
%if not instance.enabled:
<div style="color:#ef0022"><strong>DISABLED</strong></div>
%end
<div class="region"><strong>Region:</strong> {{instance.r_id}}</div>
%if instance.strategy is not None:
<div class="strategy"><strong>Strategy:</strong> {{instance.strategy}} </div>
%end
<div class="envelopes">
<h2>Occupancy Envelopes</h2>
%count=0
%for ls_id, gif_exists in envelopes_present:
<h3> Lifestage "{{ls_id}}" </h3>
%if gif_exists is not None: # show animation!
<img class="gifanimation" src="{{idx}}/{{ls_id}}/envelope.gif"/>
%if instance.is_complete(): # Only show generate button if instance is complete
<form action="{{idx}}/{{ls_id}}/envelope.gif" method="post">
<input type="hidden" name="envelope" value="{{ls_id}}"/></td>
%ts = instance.get_envelopes_timestamp() 
%if ts is not None and gif_exists < ts or not instance.are_envelopes_newer_than_reps():
<p>This envelope animation appears to be out of date: <input type="submit"
value="Regenerate envelope"/></form></p>
%else:
<p>If you believe this image doesn't reflect the latest simulations: <input type="submit"
value="Regenerate envelope"/></form></p>
%end # out of date
%else:
<p>To regenerate the occupancy envelope, all replicates in instance must be run.
Currently {{instance.get_num_remaining_reps()}} replicates are incomplete, or
haven't been run.</p>
%end # is instance complete
%else: # gif does not exist
%if instance.is_complete(): # Only show generate button if instance is complete
<form action="{{idx}}/{{ls_id}}/envelope.gif" method="post">
<input type="hidden" name="envelope" value="{{ls_id}}"/></td>
<p>No occupancy envelope animation has been generated. <input type="submit"
value="Generate envelope"/></form></p>
%else:
<p>To generate the occupancy envelope, all replicates in instance must be run.
Currently {{instance.get_num_remaining_reps()}} replicates are incomplete, or
haven't been run.</p>
%end # is instance complete
%end # gif exists
%map_pack_exists = map_packs_present[count][1]; count += 1
%if map_pack_exists is not None:
<a href="{{idx}}/{{ls_id}}/map_pack.zip">Download these envelopes as a zip file of GeoTIFFs</a>
%if instance.is_complete(): # Only show generate button if instance is complete
<form action="{{idx}}/{{ls_id}}/map_pack.zip" method="post">
<input type="hidden" name="map_pack" value="{{ls_id}}"/></td>
%ts = instance.get_envelopes_timestamp() 
%if ts is not None and map_pack_exists < ts or not instance.are_envelopes_newer_than_reps():
<p>The available map pack appears to be out of date: <input type="submit"
value="Regenerate map pack"/></form></p>
%else:
<p>If you believe this map pack doesn't reflect the latest simulations: <input type="submit"
value="Regenerate map pack"/></form></p>
%end # out of date
%else: # not complete
<p>To regenerate the map pack, all replicates in instance must be run.
Currently {{instance.get_num_remaining_reps()}} replicates are incomplete, or
haven't been run.</p>
%end # is instance complete
% else:
%if instance.is_complete(): # Only show generate button if instance is complete
<form action="{{idx}}/{{ls_id}}/map_pack.zip" method="post">
<input type="hidden" name="map_pack" value="{{ls_id}}"/></td>
<p>No map pack has been generated. <input type="submit"
value="Generate"/></form></p>
%else: # not complete
<p>To generate a map pack, all replicates in instance must be run.
Currently {{instance.get_num_remaining_reps()}} replicates are incomplete, or
haven't been run.</p>
%end # is instance complete
%end
%end
</div>
%if instance.var_keys is not None:
<div class="variables">
<strong>Variables:</strong><ul>
%for vv in zip(instance.var_keys,instance.variables):
<li> {{vv[0]}} - {{vv[1]}} </li>
%end
</ul></div>
%end
</div>
<div class="replicates">
<h2> Replicates </h2>
<p><strong># complete/total:</strong> {{len([x for x in instance.replicates if x.complete])}} / {{instance.experiment.get_num_replicates()}}</p>
%if len(instance.activeReps) > 0:
<h3> Active </h3>
<p> \\
% for r in range(0,len(instance.activeReps)):
<a href="/models/{{instance.experiment.get_name()}}/instances/{{idx}}/replicates/{{r}}">{{str(r)}}</a>
% end
</p>
%end
<div class="replicate-list">
% for r in range(0,len(instance.replicates)):
<a href="/models/{{instance.experiment.get_name()}}/instances/{{idx}}/replicates/{{r}}">{{str(r)}}</a>
% end
</div>
</div>
</body>
</html>
