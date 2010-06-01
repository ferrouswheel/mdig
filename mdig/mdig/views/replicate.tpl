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
%include status_headline task_updates=task_updates, task_order=task_order
<h1><a href="/models/{{instance.experiment.get_name()}}">{{instance.experiment.get_name()}}</a> - <a href="/models/{{instance.experiment.get_name()}}/instances/{{idx}}">Instance {{idx}}</a> - Replicate {{rep_num}}</h1>
<div class="details">
<div class="region"><strong>Region:</strong> {{instance.r_id}}</div>
%if instance.strategy is not None:
<div class="strategy"><strong>Strategy:</strong> {{instance.strategy}} </div>
%end
<div class="Maps">
<h2>Maps</h2>
%for ls_id, gif_exists in gifs_present:
<h3> Lifestage "{{ls_id}}" </h3>
%if gif_exists: # show animation!
<img class="gifanimation" src="{{rep_num}}/{{ls_id}}/spread.gif"/>
<form action="" method="post">
<input type="hidden" name="gif" value="{{ls_id}}"/></td>
<p>If you believe this animation doesn't reflect the latest simulations: <input type="submit"
value="Regenerate animation"/></form></p>
% else:
<form action="" method="post">
<input type="hidden" name="gif" value="{{ls_id}}"/></td>
<p>No animation has been generated. <input type="submit"
value="Generate animation"/></form></p>
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
