"""Verified bilingual identities. Never merge projects by fuzzy similarity alone."""
import re
ALIASES=[{
 'department':'土木工程拓展署','reference_no':'CE 43/2026 (CE)',
 'title_zh':'优化港岛北维多利亚港海滨 – 设计及建造',
 'title_en':'Enhancement of Victoria Harbour Waterfront on Hong Kong Island North – Design and Construction',
 'evidence_url':'https://www.cedd.gov.hk/eng/tender-notices/consultancy-agreements/invitation-for-technical-and-fee-proposals/index-id-1372.html',
}]

def normalized_title(value):
    value=re.sub(r'^(?:招标承投|Invitation to Tender for|Tender for)\s*','',value,flags=re.I)
    return re.sub(r'[\W_]','',value).casefold()

def apply_identity(row):
    key=normalized_title(row['title'])
    for alias in ALIASES:
        if row['department']==alias['department'] and key in [normalized_title(alias['title_zh']),normalized_title(alias['title_en'])]:
            row['reference_no']=row.get('reference_no') or alias['reference_no']
            row['title_zh']=alias['title_zh']
            row['title_aliases']=[alias['title_zh'],alias['title_en']]
            row['identity_evidence_url']=alias['evidence_url']
    return row
