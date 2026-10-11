"""Mocks only. This test suite never reaches QQ Music production endpoints."""
from __future__ import annotations
import asyncio
import json
import pytest
from qqmusicmcp import writes
from qqmusicmcp.write_backend import WriteBackend, csrf_token

@pytest.fixture()
def example(monkeypatch):
    library = [
        {'directory_id': 201, 'playlist_id': 11, 'name': '我喜欢', 'song_count': 2},
        {'directory_id': 400, 'playlist_id': 42, 'name': '测试', 'song_count': 1},
        {'directory_id': 401, 'playlist_id': 43, 'name': '空歌单', 'song_count': 0},
    ]
    tracks = {11:[{'mid':'X','song_id': 100,'type':0},{'mid':'Y','song_id': 101,'type':0}],
              42:[{'mid':'X','song_id': 100,'type':0}],
              43:[]}
    async def list_playlists(): return [dict(x) for x in library]
    async def list_tracks(pid): return [dict(x) for x in tracks[pid]]
    async def likes():
        return {'songs': tracks[11], 'playlist': library[0]}
    monkeypatch.setattr(writes, 'personal_playlists', list_playlists)
    monkeypatch.setattr(writes, 'playlist_tracks', list_tracks)
    monkeypatch.setattr(writes, 'liked_songs', likes)
    class FakeBackend:
        async def create_playlist(self, name):
            new_id=max(x['directory_id'] for x in library)+1
            new_pid=max(tracks)+1
            library.append({'directory_id':new_id,'playlist_id':new_pid,'name':name,'song_count':0})
            tracks[new_pid]=[]
            return new_id
        async def edit_song(self, action, directory_id, song_id, song_type=0):
            p=next(x for x in library if x['directory_id']==directory_id)
            lst=tracks[p['playlist_id']]
            if action=='add': lst.append({'mid':'TEST','song_id':song_id,'type':song_type})
            else: lst[:]=[x for x in lst if x['song_id']!=song_id]
            p['song_count']=len(lst)
        async def delete_playlist(self, directory_id):
            p=next(x for x in library if x['directory_id']==directory_id)
            if tracks[p['playlist_id']]: raise ValueError('not empty')
            library.remove(p)
    return library, tracks, FakeBackend()

def test_csrf_token_matches_expected():
    assert csrf_token('p_skey=abc') == csrf_token('uin=o123; p_skey=abc')
    assert csrf_token('') == 5381

@pytest.mark.asyncio
async def test_preview_does_not_write_or_modify_likes(example):
    _, tracks, backend=example
    gate=writes.WriteGate(backend)
    with pytest.raises(ValueError, match='My Likes'):
        await gate.preview('remove_song',directory_id=201,song_id=100)
    with pytest.raises(ValueError, match='non-empty'):
        await gate.preview('delete_playlist',directory_id=400)
    previous=list(tracks[42])
    preview=await gate.preview('remove_song',directory_id=400,song_id=100)
    assert preview['status']=='preview_only'
    assert tracks[42]==previous

@pytest.mark.asyncio
async def test_apply_disabled_by_default(example, monkeypatch):
    _,_,backend=example
    monkeypatch.delenv('QQMUSIC_ENABLE_WRITES',raising=False)
    gate=writes.WriteGate(backend)
    preview=await gate.preview('create_playlist',name='新建')
    with pytest.raises(PermissionError):
        await gate.apply(preview['confirmation_token'])

@pytest.mark.asyncio
async def test_create_add_remove_delete_verified(example,monkeypatch):
    library, tracks, backend=example
    monkeypatch.setenv('QQMUSIC_ENABLE_WRITES','true')
    monkeypatch.setattr(writes,'probe_valid',lambda: True)
    gate=writes.WriteGate(backend)
    a=await gate.preview('create_playlist',name='新建')
    done=await gate.apply(a['confirmation_token'])
    directory_id=done['directory_id']
    b=await gate.preview('add_song',directory_id=directory_id,song_id=101)
    assert (await gate.apply(b['confirmation_token']))['status']=='verified'
    c=await gate.preview('remove_song',directory_id=directory_id,song_id=101)
    assert (await gate.apply(c['confirmation_token']))['status']=='verified'
    d=await gate.preview('delete_playlist',directory_id=directory_id)
    assert (await gate.apply(d['confirmation_token']))['status']=='verified'
    assert all(x['directory_id']!=directory_id for x in library)

@pytest.mark.asyncio
async def test_refuse_stale_preview_and_replay(example,monkeypatch):
    library,tracks,backend=example
    monkeypatch.setenv('QQMUSIC_ENABLE_WRITES','true')
    monkeypatch.setattr(writes,'probe_valid',lambda: True)
    gate=writes.WriteGate(backend)
    ticket=await gate.preview('remove_song',directory_id=400,song_id=100)
    tracks[42].append({'mid':'Y','song_id':101,'type':0})
    library[1]['song_count']+=1
    with pytest.raises(ValueError,match='changed after preview'):
        await gate.apply(ticket['confirmation_token'])
    with pytest.raises(ValueError,match='already used'):
        await gate.apply(ticket['confirmation_token'])

@pytest.mark.asyncio
async def test_probe_mock_disposable_playlist(example, monkeypatch, tmp_path):
    library, tracks, backend=example
    monkeypatch.setenv('QQMUSIC_ENABLE_WRITES','true')
    called=[]
    monkeypatch.setattr(writes,'_save_probe',lambda: called.append('success'))
    result=await writes.run_temporary_probe(backend)
    assert result['status']=='passed'
    assert called==['success']
    assert len(library)==3
    assert len(tracks[11])==2

@pytest.mark.asyncio
async def test_no_probe_without_flag(example, monkeypatch):
    monkeypatch.delenv('QQMUSIC_ENABLE_WRITES',raising=False)
    with pytest.raises(PermissionError):
        await writes.run_temporary_probe(example[2])
