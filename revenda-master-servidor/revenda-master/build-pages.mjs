import { cp, mkdir, readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const seed = existsSync(resolve(root, 'backend/seed')) ? resolve(root, 'backend/seed') : resolve(root, 'seed');
const output = resolve(process.argv[2] || 'pages');
const asset = name => resolve(output, 'assets', name);
await mkdir(output, { recursive: true });
await cp(resolve(root, 'frontend/assets'), asset(''), { recursive: true, filter: file => !file.endsWith('admin.js') });
await cp(resolve(seed, 'images'), asset('catalog'), { recursive: true });
const vehicles = JSON.parse(await readFile(resolve(seed, 'vehicles.json'), 'utf8')).map((vehicle, index) => {
  const photos = vehicle.photos.map((file, position) => ({
    id: position + 1,
    url: './assets/catalog/' + encodeURIComponent(file)
  }));
  return { ...vehicle, id: index + 1, photos, photo: photos[0]?.url ?? null };
});
const brands = ['Chevrolet', 'Volkswagen', 'Fiat', 'Jeep', 'Hyundai', 'Toyota', 'Honda', 'Renault'];
const sort = values => [...new Set(values)].sort((a, b) => a.localeCompare(b, 'pt-BR'));
const metadata = {
  brands,
  models_by_brand: Object.fromEntries(brands.map(brand => [brand, sort(vehicles.filter(car => car.brand === brand).map(car => car.model))])),
  years: [...new Set(vehicles.map(car => car.year))].sort((a, b) => b - a),
  colors: sort(vehicles.map(car => car.color).filter(Boolean)),
  transmissions: ['Manual', 'Automático'],
  whatsapp: (process.env.WHATSAPP_NUMBER || '').replace(/\D/g, ''),
  address: process.env.STORE_ADDRESS || 'Av. Imperial, 1200, Centro'
};
for (const name of ['index.html', 'veiculo.html']) {
  const html = (await readFile(resolve(root, 'frontend', name), 'utf8'))
    .replaceAll('"/assets/', '"./assets/')
    .replaceAll('href="/"', 'href="./"')
    .replace('<script src="./assets/js/rm.js"></script>', '<script src="./assets/js/rm.js"></script>\n<script src="./assets/js/catalogo-pages.js"></script>');
  await writeFile(resolve(output, name), html);
}
const detailPath = asset('js/veiculo.js');
await writeFile(detailPath, (await readFile(detailPath, 'utf8')).replace('urlVoltar || "/"', 'urlVoltar || "./"'));
await writeFile(asset('js/catalogo-pages.js'), `(() => {
  const vehicles = ${JSON.stringify(vehicles)};
  const metadata = ${JSON.stringify(metadata)};
  RM.config.linkVeiculo = id => './veiculo.html?id=' + encodeURIComponent(id);
  RM.api = {
    meta: async () => metadata,
    vehicles: async filters => {
      const items = vehicles.filter(car => Object.entries(filters || {}).every(([key, value]) =>
        !value || String(car[key]).toLocaleLowerCase('pt-BR') === String(value).toLocaleLowerCase('pt-BR')));
      return { items, count: items.length };
    },
    vehicle: async id => {
      const result = vehicles.find(car => String(car.id) === String(id));
      if (!result) throw Object.assign(new Error('Veículo não encontrado.'), { status: 404 });
      return result;
    }
  };
})();\n`);
await writeFile(resolve(output, '.nojekyll'), '');
