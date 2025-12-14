import sitemap from 'routes/sitemap';

// --- 1. Filter out unwanted items from sitemap ---
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const unfilteredTopList = sitemap.filter((item: any) => { 
  const id = item.id;
  if (
    id === 'template-pages' ||
    id === 'settings' ||
    id === 'account-settings' ||
    id === 'authentication' ||
    id === 'users' || 
    id === 'pricing' ||
    id === 'integrations'
  ) {
    return null;
  }
  return item;
});

// --- 2. RENAME 'Features' to 'Admin Panel' & Add Calibration & Smart Control & Camera2 ---
// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const finalTopList: any[] = [];

// @ts-ignore
// eslint-disable-next-line @typescript-eslint/no-explicit-any
unfilteredTopList.forEach((item: any) => {
  const isFeatures = item.subheader === 'Features';
  
  if (isFeatures) {
    // 2.1 Admin Panel
    finalTopList.push({
      ...item,
      subheader: 'Admin Panel', 
      path: '/admin',          
      icon: 'fluent:person-key-24-filled', 
    });

    // 2.2 Calibration (Camera 1)
    finalTopList.push({
      id: 'calibration',
      subheader: 'Calibration Camera 1',
      path: '/calibration',
      icon: 'mdi:target-variant', 
    });

    // ✅✅✅ 2.3 Calibration Camera 2 (เพิ่มใหม่)
    finalTopList.push({
      id: 'calibration-cam2',
      subheader: 'Calibration Camera 2',
      path: 'calibration-camera-2',
      icon: 'mdi:target-variant',
    });

    // 2.4 Smart Control (Camera 1)
    finalTopList.push({
      id: 'smart-control',
      subheader: 'Smart Control',
      path: '/smart-control',
      icon: 'mdi:gesture-tap',
    });

    // 2.5 Smart Control (Camera 2) - ใหม่!
    finalTopList.push({
      id: 'smart-control-cam2',
      subheader: 'Smart Control Camera 2',
      path: '/smart-control-camera-2',
      icon: 'mdi:gesture-tap',
    });

  } else {
    finalTopList.push(item);
  }
});

export const topListData = finalTopList;

// --- 3. Bottom List & Profile List ---
export const bottomListData = sitemap.filter(() => false);
export const profileListData = null;
