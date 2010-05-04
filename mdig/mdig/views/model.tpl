<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>MDiG - {{model.get_name()}}</title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
<style type="text/css">
table, td, th
{
border:1px solid green;
text-align:center;
}
td
{
padding:10px;
}
th
{
background-color:green;
color:white;
padding: 0px 10px;
}
</style>
</head>
<body>
<div class="description">
<h1>{{model.get_name()}}</h1>
<p>{{model.get_description()}}</p>
</div>
<div class="lifestages">
<h2>Lifestages</h2>
%for ls_id in model.get_lifestage_ids():
<div class="lifestage">
<h3>Lifestage "{{ls_id}}"</h3>
% ls = model.get_lifestage(ls_id)
<p><strong>Phenology:</strong> <ul>
%for r_id in model.get_region_ids(): 
<li>
region {{r_id}}: {{ls.getPhenologyBins(r_id)}}
</li>
%end
</ul>
</p>
<div class="events"><h4>Events</h4>
<ol>
%for e in ls.events:
<li>{{e.get_command()}} - {{str(e.get_params(True,None))}} </li>
%end
</ol>
</div>
</div>
%end
</div>
<div class="model-list">
<h2>Instances</h2>
<form action="/models/{{model.get_name()}}" method="post">
<table style="border-collapse: collapse">
<thead style="background-color: #aaaaaa"><th>Index</th>
<th>Enabled?</th>
<th>Region</th>
<th>Strategy</th>
% vars = model.get_variable_values()
%if len(vars) > 0:
<th colspan="{{len(vars.keys())}}">Variables</th>
%else:
<th>Variables</th>
%end
<th>Replicates</th>
<th>Active</th>
</thead>
%if len(vars) > 0:
<tr class="subheading">
<th></th><th></th><th></th><th></th>
%for v in vars.keys():
<th>{{v}}</th>
%end
<th></th><th></th>
</tr>
%end
% i=0
%for instance in model.get_instances():
    <tr>
    <td><a href="{{model.get_name()}}/instances/{{i}}">{{i}}</a></td>
    <td> \\
%if instance.enabled:
<input type="checkbox" name="enabled" value="{{i}}" checked/></td>
%else:
<input type="checkbox" name="enabled" value="{{i}}"/></td>
%end
% i=i+1
    <td>{{instance.r_id}}</td>
    <td> \\
%if instance.strategy is not None:
{{instance.strategy}}
%else:
None
%end
</td>
%if instance.var_keys is not None:
%for vv in instance.variables:
<td> {{str(vv)}} </td>
%end
%else:
<td> None </td>
%end
    <td>{{len([x for x in instance.replicates if x.complete])}}/{{model.get_num_replicates()}}</td>
    <td> \\
%if len(instance.activeReps) > 0:
Yes
%else:
No
%end
</td>
    </tr>
%end
</table>
<input type="submit" value="Update enabled status"/>
</form>
</div>
</body>
</html>
