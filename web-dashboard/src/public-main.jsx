import React from 'react';
import ReactDOM from 'react-dom/client';
import Site from './Site';
import { siteLayout } from './siteLayout';
import './styles.css';

// The Cloudflare site has no database, inventory worker, or administrator login.
const data = { config: siteLayout, status: null, loading: false };
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode><Site data={data} /></React.StrictMode>,
);
