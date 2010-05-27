<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>MDiG - {{instance.experiment.get_name()}} - Instance {{idx}} </title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
%include css
</head>
<body>
%include status_headline task_updates=task_updates, task_order=task_order
<h1><a href="/models/{{instance.experiment.get_name()}}">{{instance.experiment.get_name()}}</a> - Instance {{idx}}</h1>
<div class="details">
%if not instance.enabled:
<div style="color:#ef0022"><strong>DISABLED</strong></div>
%end
<div class="region"><strong>Region:</strong> {{instance.r_id}}</div>
%if instance.strategy is not None:
<div class="strategy"><strong>Strategy:</strong> {{instance.strategy}} </div>
%end
<div class="envelopes">
<h2>Occupancy Envelope</h2>
%for ls_id, gif_exists in envelopes_present:
<h3> Lifestage "{{ls_id}}" </h3>
%if gif_exists: # show animation!
<img src="{{idx}}/{{ls_id}}/envelope.gif"/>
<form action="" method="post">
<input type="hidden" name="envelope" value="{{ls_id}}"/></td>
<p>If you believe this image doesn't reflect the latest simulations: <input type="submit"
value="Regenerate envelope"/></form></p>
% else:
<form action="" method="post">
<input type="hidden" name="envelope" value="{{ls_id}}"/></td>
<p>No occupancy envelope animation has been generated. <input type="submit"
value="Generate envelope"/></form></p>
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
