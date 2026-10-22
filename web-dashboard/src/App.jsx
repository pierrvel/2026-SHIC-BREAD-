import Site from './Site';
import AdminView from './components/AdminView';
import { isLocal, isSample, inventoryEnabled } from './firebase';
import { useVending } from './useVending';

// Legacy inventory dashboard, also used by the optional local Pi runtime.
export default function App() {
  const data = useVending();
  return <Site data={data} inventoryEnabled={inventoryEnabled} isLocal={isLocal} isSample={isSample}
    renderAdmin={(props) => <AdminView {...props} />} />;
}
