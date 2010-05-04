<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{{name}}</title>
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
<h1>Modular Dispersal in GIS</h1>
<p>You can browse, run, analyse and export existing spread models, or submit a new model
description.</p>
</div>
<div class="model-list">
<h2>Model Repository</h2>
<p><small>Repository location: {{repo_location}}</small></p>
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
</div>
<div class="footer">
<p class="copyright">
Copyright 2005-2010 Dr. Joel Pitt<br/>
Copyright 2008-2009 AgResearch<br/>
Copyright 2005-2007,2010 Lincoln University<br/>
</p>
</div>
</body>
</html>
