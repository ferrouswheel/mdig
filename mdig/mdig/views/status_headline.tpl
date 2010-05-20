%if len(task_order) > 0:
<div class="status"> <em>Tasklist:</em> <ul>
%for m_name,task in task_order:
%if 'complete' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Completed at: {{task_updates[m_name][task]['complete']}} </li>
%elif 'percent_complete' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Instance {{task_updates[m_name][task]['active'][0]}} - Percent complete: {{task_updates[m_name][task]['percent_complete']}}%. </li>
%elif 'active' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Instance {{task_updates[m_name][task]['active']}} active. </li>
%elif 'started' in task_updates[m_name][task]:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - Started at task_updates[m_name][task]['started'] </li>
%else:
<li>Model <a href="/models/{{m_name}}">{{m_name}}</a> - Task: {{task}} - In queue. </li>
%end
</ul>
</div>
%end
