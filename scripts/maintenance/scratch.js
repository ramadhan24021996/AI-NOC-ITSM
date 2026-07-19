fetch("http://localhost:44600/api/fleet/admin/storage")
  .then(r => r.json())
  .then(data => console.log(data))
  .catch(e => console.error("Err", e));
