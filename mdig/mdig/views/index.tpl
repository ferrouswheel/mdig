<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{{name}}</title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
<style type="text/css">
body {
font-family:"Arial";
}
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
<h1>Modular Dispersal in GIS</h1>
<p>Version {{version}} "{{v_name}}" - <a href="http://fruitionnz.com/mdig">website</a></p>
<p>You can browse, run, analyse and export existing spread models, or submit a new model
description.</p>
</div>
<div class="repository">
<h2>Model Repository</h2>
<h3> Submit a model </h3>
<form action="/models/" method="post">
<h3> Existing models </h3>
<table>
<thead><th>Model name</th><th>Description</th></thead>
<tbody>
%for m in models:
<tr>
    <td><a href="models/{{m[0]}}"><strong>{{m[0]}}</strong></a></td><td>{{m[1]}}</td>
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
