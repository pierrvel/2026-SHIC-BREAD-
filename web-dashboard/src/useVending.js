import { useEffect, useState } from 'react';
import { subscribeConnection, subscribeNode, subscribeHealth } from './firebase';

export function useVending() {
  const [config, setConfig] = useState(null);
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const [health, setHealth] = useState(null);
  const [loaded, setLoaded] = useState({ config: false, status: false });
  const [errors, setErrors] = useState({});
  useEffect(() => {
    const removers = ['config', 'status'].map((path) => subscribeNode(path, (value) => {
      (path === 'config' ? setConfig : setStatus)(value);
      setLoaded((old) => ({ ...old, [path]: true }));
      setErrors((old) => ({ ...old, [path]: null }));
    }, (error) => {
      setLoaded((old) => ({ ...old, [path]: true }));
      setErrors((old) => ({ ...old, [path]: error.message }));
    }));
    removers.push(subscribeConnection(setConnected));
    removers.push(subscribeHealth(setHealth));
    return () => removers.forEach((remove) => remove());
  }, []);
  return { config, status, health, connected, loading: !loaded.config || !loaded.status, error: Object.values(errors).find(Boolean) };
}
