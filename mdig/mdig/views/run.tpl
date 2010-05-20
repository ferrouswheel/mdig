<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>MDiG - Running {{model.get_name()}}</title>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <!--<link rel="stylesheet" href="css/style.css" type="text/css" /> -->
%if not complete:
    <meta http-equiv="refresh" content="5; url=/models/{{model.get_name()}}">
%end
%include css
</head>
<body>
%include status_headline task_updates=task_updates, task_order=task_order
<div class="description">
%if not complete:
<h1>Running model {{model.get_name()}} added to queue</h1>
%if already_exists:
%   if started:
<p>The model is already running.</p>
%   else:
<p>The model is already in queue waiting to be run. The queue has {{queue_size}} earlier tasks to complete first.</p>
%   end
%else:
%   if queue_size > 0:
<p>The model has been added to the work queue. The queue has {{queue_size}} earlier tasks to complete first.</p>
%   end
%end
<p>You will shortly be returned to the model page which will display the active
model. <a href="/models/{{model.get_name()}}">Or click to go there right now</a>.</p>
%else:
<h1>Model {{model.get_name()}} has already been completed.</h1>
<form action="/models/{{model.get_name()}}/run" method="post">
<input type="hidden" name="rerun" value="true"/><input
type="submit" value="Click here to overwrite existing results and run anyway"/>
</form>
<p>...or <a href="/models/{{model.get_name()}}">return to the model's page</a>.</p>
%end
</div>
</body>
</html>
