%if len(task_order) >= 0:
<div class="status"> <ul>
<li>[FAKE] MODEL <a href="/models/bdavidii_climate">bdavidii_climate</a> - TASK: RUN - COMPLETED AT sadasdasd</li>
%for m_name,task in task_order:
<li>MODEL <a href="/models/{{m_name}}">{{m_name}}</a> - TASK: {{task}} - COMPLETED AT {{task_updates[m_name][task]['complete']}} </li>
%end
</ul>
</div>
%end
