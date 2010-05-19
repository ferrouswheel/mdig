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
<div class="strategy"><strong>Strategy:</strong> \\
%if instance.strategy is not None:
{{instance.strategy}} </div>
%else:
None </div>
%end
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
