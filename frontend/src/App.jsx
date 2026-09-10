import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_BASE_URL || ''
const FEEDBACK_ENABLED = false
const picks = [
  ['OK Computer','Radiohead','Restless guitars, electronic detail, and widescreen songwriting reward the kind of focused listening your library suggests.','Lightly familiar','Listening pattern',['#8ca7a1','#d8e2df']],
  ['ANTI','Rihanna','A dark, intimate pop record whose adventurous production reaches beyond the smash-hit singles.','New to you','Taste crossover',['#8b1d28','#d7b79a']],
  ['Master of Puppets','Metallica','Thrash Metal precision meets ambitious song structures, making this a natural fit for your heavier listening.','Somewhat familiar','Genre connection',['#9a2f25','#161719']],
  ['House of Balloons','The Weeknd','Nocturnal production and emotionally raw songwriting connect the atmospheric Darkwave and R&B sides of your taste.','New to you','Mood match',['#202020','#b9b5ad']],
  ['Lateralus','TOOL','Patient builds, intricate rhythms, and immersive sequencing suit your interest in albums designed as complete journeys.','Lightly familiar','Listening pattern',['#7f2e26','#d4a05b']],
  ['Graduation','Kanye West','Bright synths, arena-sized hooks, and ambitious production make this an accessible bridge between anthemic Hip-Hop and electronic Pop.','Lightly familiar','Taste crossover',['#8a58a5','#e76f9e']],
  ['To Pimp a Butterfly','Kendrick Lamar','Dense storytelling and live-band arrangements bring together adventurous Hip-Hop, Jazz, Funk, and Soul.','Somewhat familiar','Taste crossover',['#262626','#d0c6ad']],
  ['Heaven or Las Vegas','Cocteau Twins','Dreamlike guitars and luminous melodies offer an inviting route into richly textured alternative music.','Lightly familiar','Related artist',['#cf5549','#efb45e']],
  ['White Pony','Deftones','Drony, cut-throat Alternative Metal meet a hazy atmosphere in a record that balances aggression with unusual emotional depth.','New to you','Genre connection',['#d6d2c8','#313334']],
  ['ASTROWORLD','Travis Scott','Layered modern production and seamless transitions turn a collection of rap songs into a vivid, immersive world.','New to you','Listening pattern',['#6b3b62','#d78555']],
].map(([album_name,artist_name,reason,familiarity_label,discovery,colors])=>({album_name,artist_name,reason,familiarity_label,discovery,colors}))

function Header({ authenticated, accountName, previewing, logout, deleteAccount, home }) {
  return <header><button className="brand" onClick={home}><i>▥</i> LINER NOTES</button><div className="header-actions">{previewing&&<button className="link" onClick={home}>← Back to home</button>}<details className="account-menu"><summary><span className="avatar" aria-hidden="true"><i/></span><span>{authenticated?accountName:'Not logged in'}</span><b aria-hidden="true">⌄</b></summary><div className="account-dropdown">{authenticated?<><button onClick={logout}>Log out <span>↗</span></button><button className="delete-option" onClick={deleteAccount}>Delete account &amp; data <span>×</span></button></>:<a href={`${API}/api/auth/login`}>Connect with Spotify <span>↗</span></a>}</div></details></div></header>
}

function Landing({ auth, preview, load, removeAccount, confirming, setConfirming, accountBusy, accountError }) {
  return <main className="landing"><section><h1>Find the albums<br/>between the lines.</h1><p className="lede">Thoughtful album recommendations shaped by what you actually listen to and interact with.</p>{auth==='authenticated'?<><div className="actions signed-in"><button className="button primary" onClick={load}>Load recommendations →</button><button className="button quiet" onClick={preview}>Preview the experience →</button></div>{confirming&&<div className="delete-confirm" role="alertdialog" aria-labelledby="delete-title"><strong id="delete-title">Delete your account and data?</strong><p>This permanently removes your saved Spotify credentials, sessions, and cached recommendation profile from Liner Notes. It cannot be undone.</p>{accountError&&<p className="account-error">{accountError}</p>}<div><button className="button danger" onClick={removeAccount} disabled={accountBusy}>{accountBusy?'Deleting…':'Yes, delete everything'}</button><button className="button quiet" onClick={()=>setConfirming(false)} disabled={accountBusy}>Cancel</button></div></div>}</>:auth==='checking'?<button className="button primary" disabled>Checking Spotify connection…</button>:<div className="actions"><a className="button primary" href={`${API}/api/auth/login`}>● Connect with Spotify ↗</a><button className="button quiet" onClick={preview}>Preview the experience →</button></div>}</section><aside className="stack"><div/><div/><div/></aside></main>
}

function Loading() {
  return <main className="state"><div className="vinyl"><i/></div><h1>Analyzing your listening history</h1><p>We’re tracing artists, albums, and listening patterns.<br/>This can take a moment the first time.</p><span className="progress"><i/></span></main>
}

function Problem({ reauth, retry }) {
  return <main className="state"><div className="status">{reauth?'↻':'!'}</div><p className="eyebrow">{reauth?'Connection expired':'Something skipped a beat'}</p><h1>{reauth?'Let’s reconnect.':'We couldn’t load your picks.'}</h1><p>{reauth?'Spotify needs your permission again before we can continue.':'Your profile is safe. Try once more, or come back in a little while.'}</p>{reauth?<a className="button primary" href={`${API}/api/auth/login`}>Reconnect Spotify ↗</a>:<button className="button primary" onClick={retry}>Try again ↻</button>}</main>
}

function Cover({ album, number }) {
  if(album.album_image_url) return <img className="cover" src={album.album_image_url} alt={`${album.album_name} album cover`}/>
  return <div className="cover placeholder" style={{'--a':album.colors?.[0]||'#455e65','--b':album.colors?.[1]||'#d5a75d'}}><b>{String(number).padStart(2,'0')}</b><i/></div>
}

function Card({ album, number, choice, choose }) {
  const options=[['interested','＋','Interested'],['no','−','Not interested'],['known','✓','Already know this']]
  return <article className="card"><Cover album={album} number={number}/><div><h2>{album.album_name}</h2><p className="artist">{album.artist_name}</p><p className="reason">{album.reason}</p><div className="card-actions"><a className={`spotify ${album.spotify_url?'':'disabled'}`} href={album.spotify_url||undefined} target="_blank" rel="noreferrer">Open in Spotify ↗</a>{FEEDBACK_ENABLED&&<div className="feedback">{options.map(([value,icon,label])=><button key={value} className={choice===value?'selected':''} onClick={()=>choose(value)} title={label} aria-label={label} aria-pressed={choice===value}><span>{icon}</span><b>{label}</b></button>)}</div>}</div></div></article>
}

function Results({ albums, demo, choices, choose, more, busy }) {
  return <main className="results">{demo&&<div className="demo">Preview mode — these picks are placeholders</div>}<section className="intro"><h1>Five albums worth your time.</h1></section><div className="grid">{albums.map((a,i)=><Card key={`${a.artist_name}-${a.album_name}`} album={a} number={i+1} choice={choices[a.album_name]} choose={v=>choose(a.album_name,v)}/>)}</div><section className="more"><p className="eyebrow">Keep digging</p><h2>There’s always another record.</h2><button className="button primary" onClick={more} disabled={busy}>{busy?'Finding five more…':'Discover 5 more →'}</button></section></main>
}

export default function App(){
  const previewRoute=location.pathname==='/preview'
  const [view,setView]=useState(previewRoute?'demo':'landing'),[auth,setAuth]=useState('checking'),[accountName,setAccountName]=useState('Spotify user'),[albums,setAlbums]=useState(previewRoute?picks.slice(0,5):[]),[choices,setChoices]=useState({}),[page,setPage]=useState(0),[busy,setBusy]=useState(false),[confirming,setConfirming]=useState(false),[accountBusy,setAccountBusy]=useState(false),[accountError,setAccountError]=useState('')
  useEffect(()=>{fetch(`${API}/api/auth/me`,{credentials:'include'}).then(r=>{if(!r.ok){setAuth('signed-out');return null}return r.json()}).then(data=>{if(data){setAccountName(data.account_name||data.spotify_user_id||'Spotify user');setAuth('authenticated')}}).catch(()=>setAuth('signed-out'));function followRoute(){if(location.pathname==='/preview'){setAlbums(picks.slice(0,5));setView('demo')}else{setAlbums([]);setChoices({});setView('landing')}}window.addEventListener('popstate',followRoute);return()=>window.removeEventListener('popstate',followRoute)},[])
  function request(){return fetch(`${API}/api/recommendations`,{method:'POST',credentials:'include'}).then(r=>{if(r.status===401)throw Error('reauth');if(!r.ok)throw Error('error');return r.json()})}
  function load(){setView('loading');return request().then(d=>{setAlbums(d);setView('results')}).catch(e=>setView(e.message))}
  function preview(){history.pushState({},'', '/preview');setAlbums(picks.slice(0,5));setView('demo');scrollTo({top:0,behavior:'smooth'})}
  function more(){setBusy(true);setChoices({});if(view==='demo'){setTimeout(()=>{const n=(page+1)%2;setPage(n);setAlbums(picks.slice(n*5,n*5+5));setBusy(false);scrollTo({top:0,behavior:'smooth'})},750)}else request().then(d=>{setAlbums(d);scrollTo({top:0,behavior:'smooth'})}).catch(e=>setView(e.message)).finally(()=>setBusy(false))}
  function logout(){fetch(`${API}/api/auth/logout`,{method:'POST',credentials:'include'}).finally(()=>{if(location.pathname!=='/')history.pushState({},'', '/');setAlbums([]);setChoices({});setAuth('signed-out');setView('landing')})}
  function removeAccount(){setAccountBusy(true);setAccountError('');fetch(`${API}/api/auth/account`,{method:'DELETE',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true})}).then(r=>{if(!r.ok)throw Error('We could not delete your account. Please try again.');setAlbums([]);setChoices({});setAuth('signed-out');setConfirming(false)}).catch(e=>setAccountError(e.message)).finally(()=>setAccountBusy(false))}
  function home(){if(location.pathname!=='/')history.pushState({},'', '/');setView('landing');setAlbums([]);setChoices({});setConfirming(false);scrollTo({top:0,behavior:'smooth'})}
  function beginDelete(){if(location.pathname!=='/')history.pushState({},'', '/');setView('landing');setConfirming(true);scrollTo({top:0,behavior:'smooth'})}
  const results=view==='results'||view==='demo'
  return <div className="app"><Header authenticated={auth==='authenticated'} accountName={accountName} previewing={view==='demo'} logout={logout} deleteAccount={beginDelete} home={home}/>{view==='loading'&&<Loading/>}{view==='landing'&&<Landing auth={auth} preview={preview} load={load} removeAccount={removeAccount} confirming={confirming} setConfirming={setConfirming} accountBusy={accountBusy} accountError={accountError}/>} {results&&<Results albums={albums} demo={view==='demo'} choices={choices} choose={(name,value)=>setChoices(c=>({...c,[name]:c[name]===value?undefined:value}))} more={more} busy={busy}/>} {(view==='error'||view==='reauth')&&<Problem reauth={view==='reauth'} retry={load}/>}<footer><p>Made for album people.</p></footer></div>
}
