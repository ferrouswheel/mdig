<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
% rep_num = instance.replicates.index(replicate)
    <title>MDiG - {{instance.experiment.get_name()}} - Instance {{idx}} -
    Replicate {{rep_num}}</title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
%include css
</head>
<body>
<small><a href="/models/">All models</a></small>
%include status_headline task_updates=task_updates, task_order=task_order
<h1><a href="/models/{{instance.experiment.get_name()}}">{{instance.experiment.get_name()}}</a> - <a href="/models/{{instance.experiment.get_name()}}/instances/{{idx}}">Instance {{idx}}</a> - Replicate {{rep_num}}</h1>
%if error:
<div class="error">
Sorry, there's been an error :-(<br/>
{{error}}
</a>
%end
<div class="details">
<div class="region"><strong>Region:</strong> {{instance.r_id}}</div>
%if instance.strategy is not None:
<div class="strategy"><strong>Strategy:</strong> {{instance.strategy}} </div>
%end
<div class="Maps">
<h2>Maps</h2>
%count=0
%for ls_id, gif_exists in gifs_present:
<h3> Lifestage "{{ls_id}}" </h3>
%if gif_exists: # show animation!
<img class="gifanimation" src="{{rep_num}}/{{ls_id}}/spread.gif"/>
<form action="{{rep_num}}/{{ls_id}}/spread.gif" method="post">
<input type="hidden" name="gif" value="{{ls_id}}"/></td>
<p>If you believe this animation doesn't reflect the latest simulations: <input type="submit"
value="Regenerate animation"/></form></p>
% else:
<form action="{{rep_num}}/{{ls_id}}/spread.gif" method="post">
<input type="hidden" name="gif" value="{{ls_id}}"/></td>
<p>No animation has been generated. <input type="submit"
value="Generate animation"/></form></p>
%end
%map_pack_exists = map_packs_present[count][1]; count += 1
%if map_pack_exists:
<a href="{{rep_num}}/{{ls_id}}/map_pack.zip">Download these maps as a zip file of GeoTIFFs</a>
<form action="{{rep_num}}/{{ls_id}}/map_pack.zip" method="post">
<input type="hidden" name="map_pack" value="{{ls_id}}"/></td>
<p>If you believe this map pack doesn't reflect the latest simulations: <input type="submit"
value="Regenerate map pack"/></form></p>
% else:
<form action="{{rep_num}}/{{ls_id}}/map_pack.zip" method="post">
<input type="hidden" name="map_pack" value="{{ls_id}}"/></td>
<p>No map pack has been generated. <input type="submit"
value="Generate"/></form></p>
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
</body>
</html>
