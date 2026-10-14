"""Typed primary-score comparison, independent of labels and prose metadata."""
from .independent import AssessmentInputError,check,equal,finite


def primary_values(value, definitions, attempted):
    rows=value['checkpoints']
    check(type(rows) is list and len(rows)==len(definitions)
          and [r.get('id') for r in rows]==[d[0] for d in definitions],'comparison-checkpoint-census')
    check(all(type(r.get('passed')) is bool and type(r.get('weight')) is int and r['weight']==d[1]
              for r,d in zip(rows,definitions)),'comparison-checkpoint-values')
    for row in rows:
        needs=row['requirements'];missing=row['not_met'];evidence=row['evidence_sequences']
        check(type(needs) is dict and bool(needs) and all(type(k) is str and k and (type(v) is bool or v is None) for k,v in needs.items()),'comparison-requirements')
        check(type(missing) is list and all(type(k) is str for k in missing)
              and len(missing)==len(set(missing)) and set(missing)=={k for k,v in needs.items() if v is not True}
              and row['passed']==all(v is True for v in needs.values()),'comparison-checkpoint-evidence')
        check(type(evidence) is list and all(type(i) is int and 1<=i<=attempted for i in evidence)
              and len(evidence)==len(set(evidence)),'comparison-evidence-indices')
    points=sum(r['weight'] for r in rows if r['passed']);full=int(all(r['passed'] for r in rows))
    total=sum(d[1] for d in definitions);partial=0.5*(points/total)+0.5*full
    check(all(type(value.get(k)) is int for k in ('points_earned','total_points','S_full'))
          and value['points_earned']==points and value['total_points']==total and value['S_full']==full
          and finite(value.get('S_partial')) and value['S_partial']==partial,'comparison-primary-arithmetic')
    return {'checkpoints':[{'id':r['id'],'weight':r['weight'],'passed':r['passed']} for r in rows],
            'points_earned':points,'total_points':total,'S_full':full,'S_partial':partial}


def compare_primary(independent, producer, definitions, attempted):
    """Agreement here is typed result agreement, not source authentication."""
    scope={'scope':'Checkpoint IDs, weights, outcomes and formula compared field by field; explanatory wording excluded',
           'contract_identity_authenticated':False,'external_contract_identity_required':True}
    if producer is None:return {'status':'unavailable','reason':'No producer primary checkpoint result',**scope}
    try:
        left=primary_values(independent,definitions,attempted)
        right=primary_values(producer,definitions,attempted)
    except AssessmentInputError as error:
        return {'status':'invalid_comparison_input','reason':error.code,**scope}
    except (KeyError,TypeError,ValueError,IndexError):
        return {'status':'invalid_comparison_input','reason':'malformed-primary-result',**scope}
    differences=[];details=[]
    for a,b in zip(left['checkpoints'],right['checkpoints']):
        for key in ('weight','passed'):
            if not equal(a[key],b[key]):differences.append({'field':a['id']+'/'+key,'independent':a[key],'producer':b[key]})
    for key in ('points_earned','total_points','S_full','S_partial'):
        if left[key]!=right[key]:differences.append({'field':key,'independent':left[key],'producer':right[key]})
    for a,b in zip(independent['checkpoints'],producer['checkpoints']):
        for key in ('requirements','not_met','evidence_sequences'):
            if not equal(a[key],b[key]):details.append({'field':a['id']+'/'+key,'independent':a[key],'producer':b[key]})
    return {'status':'disagreement' if differences else 'agreement','disagreements':differences,
            'evidence_differences':details,**scope}
