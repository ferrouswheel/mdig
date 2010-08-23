<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>MDiG - {{model.get_name()}}</title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
%include css
</head>
<body>
<small><a href="/models/">All models</a></small>
%include status_headline task_updates=task_updates, task_order=task_order
<div class="description">
<h1>{{model.get_name()}}</h1>
<p>{{model.get_description()}}</p>
</div>
%if len(missing_resources) > 0:
<div> <span class="error">Warning:</span> This model is missing resources:
<ul>
%for i in missing_resources:
<li>{{i[1]}} [{{i[0]}}
%if i[0] == 'map':
<a href="http://fruitionnz.com/mdig/index.php?title=Importing_maps">?</a>]</li>
%elif i[0] == 'region':
<a href="http://fruitionnz.com/mdig/index.php?title=Adding_Regions">?</a>]</li>
%elif i[0] == 'popmod':
<a href="http://fruitionnz.com/mdig/index.php?title=Adding_lifestage_files">?</a>]</li>
%elif i[0] == 'coda':
<a href="http://fruitionnz.com/mdig/index.php?title=Adding_lifestage_files">?</a>]</li>
%end
%end
</ul>
</div>
%end
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
        <li> {{e.get_command()}}
            <ul>
% params = e.get_params(True,None)
% vars = model.get_variable_values() 
%for p in params:
                <li> {{p}}: \\
%if params[p][1] != None:
%if params[p][0] == 'VALUE':
{{params[p][1]}}
%elif params[p][0] == 'VAR':
variable <i>{{params[p][1]}}</i> has values {{vars[params[p][1]]}}
%else:
{{params[p][1]}} [<i>{{params[p][0]}}</i>]
%end
%else:
{{params[p][0]}}
%end
</li>
%end
            </ul>
        </li>
%end
    </ol>
</div>
</div>
%end
</div>
<div class="model-list">
<h3>Actions</h3>
<div>
%if len(missing_resources) > 0:
<strong>Run Model</strong> - <i>please resolve missing resources in order to run model</i>
%else:
<form action="/models/{{model.get_name()}}/run" method="post">
<strong>Run Model</strong> -  <input type="submit" value="Run all"/>
</form>
%end
</div>
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
<th>Occ. envelope</th>
<th>Active</th>
</thead>
%if len(vars) > 0:
<tr class="subheading">
<th></th><th></th><th></th><th></th>
%for v in vars.keys():
<th>{{v}}</th>
%end
<th></th><th></th><th></th>
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
    <td>{{instance.r_id}}</td>
    <td> \\
%if instance.strategy is not None:
{{instance.strategy}}
%else:
-
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
%if instance.get_occupancy_envelopes(nolog=True) is None:
-
%else:
Yes
%end
    </td>
    <td> \\
%if i in active_instances:
Yes
%else:
No
%end
</td>
</tr>
% i=i+1
%end
</table>
<input type="submit" value="Update enabled status"/>
</form>
</div>
</body>
</html>
