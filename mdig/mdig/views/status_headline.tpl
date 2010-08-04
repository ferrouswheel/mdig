%if len(task_order) > 0:
<div class="status"> <em>Tasklist:</em> <ul>
%for m_name,task in task_order:
<!-- setup active instance varable -->
% u = task_updates[m_name][task] 
%ti = None
%if 'active_instance' in u: ti = u['active_instance']
<!-- debug output {{u}} -->
<li> Model <a href="/models/{{m_name}}">{{m_name}}</a> -
Task: {{task}} -
%if ti is not None:
Instance <a href="/models/{{m_name}}/instances/{{ti}}">{{ti}}</a> -
%end
%if 'error' in u:
<span class="error">ERROR: {{u['error']}}</span>. If you keep getting this, email <a href="mailto:mdig-users@googlegroups.com">mdig-users@googlegroups.com</a>.
%else: # no error
%if 'complete' in u:
 Completed at: {{u['complete'].strftime("%H:%M:%S %d/%m/%y")}}
%elif 'started' in u:
 Started at {{u['started'].strftime("%H:%M:%S %d/%m/%y")}}
%if 'percent_done' in u:
 Percent complete: {{u['percent_done']}}%.
%end
%end
%if 'approx_q_pos' in u:
 Position {{u['approx_q_pos']+1}} in queue.
%end
%end # error
%if 'status' in u: 
 Status: {{u['status']}}
%end
</li>
%end
</ul>
</div>
%end
