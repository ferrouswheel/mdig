<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{{name}}</title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <meta http-equiv="content-script-type" content="text/javascript">
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
%include css
</head>
<body>
<div class="description">
<h1>Modular Dispersal in GIS</h1>
<p>Version {{version}} "{{v_name}}" - <a href="http://fruitionnz.com/mdig">website</a></p>
<p>You can browse, run, analyse and export existing spread models, or submit a new model
description.</p>
</div>
<div class="repository">
<h2>Model Repository</h2>
%include status_headline task_updates=task_updates, task_order=task_order
<h3> Submit a model </h3>
<form action="/models/" method="post" enctype="multipart/form-data" >
<input type="file" name="new_model" size="50"><input type="submit" value="Upload">
</form>
<h3> Existing models </h3>
<table>
<thead><th>Model name</th><th>Description</th><th>Delete</th></thead>
<tbody>
<FORM ACTION="/models/" METHOD="POST" NAME="del" id="del">
<INPUT TYPE="HIDDEN" NAME="confirm" VALUE="false" id="del_confirm">
</FORM>
<script type="text/javascript">
function delete_model(model_name) {
var answer = confirm("Are you sure you wish to delete the model " + model_name
        + " and ALL simulation results? There is NO undo..." );
if (answer)
    var del = document.getElementById('del');
    del.action = "/models/" + model_name +"/del";
    document.getElementById('del_confirm').value=true;
    del.submit();
}
</script>
%for m in models:
<tr>
    <td><a href="models/{{m[0]}}"><strong>{{m[0]}}</strong></a></td><td>{{m[1]}}</td>
    <td><a href="models/{{m[0]}}" onClick="delete_model({{m[0]}}); return false;">x<a></td>
</tr>
%end
</tbody>
</table>
<p class="rdetails"><small>Repository directory: {{repo_location}}</small> | <small>GRASS details - GRASSDB: {{grass_env["GISDBASE"]}}, Location:
{{grass_env["LOCATION_NAME"]}}, Mapset: {{grass_env["MAPSET"]}}</small></p>
</div>
<div class="footer">
<p class="copyright">
&copy; 2005-2010 <a href="http://ferrouswheel.me">Dr. Joel Pitt</a><br/>
&copy; 2005-2007, 2010 <a href="http://lincoln.ac.nz">Lincoln University</a><br/>
</p>
</div>
</body>
</html>
