"""Bounded local login throttle; deploy an edge limit across multiple API replicas."""
from collections import OrderedDict
from time import monotonic
from fastapi import HTTPException
attempts=OrderedDict()
def attempt(ip,email):
    now=monotonic();key=(ip,email)
    count,expiry=attempts.pop(key,(0,now+300))
    if expiry<now:count,expiry=0,now+300
    attempts[key]=(count+1,expiry)
    while len(attempts)>10000:attempts.popitem(last=False)
    if count>=10:raise HTTPException(429,'Too many sign-in attempts. Try again in five minutes.')
