import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../portal/app.js',import.meta.url),'utf8');
const html=readFileSync(new URL('../portal/index.html',import.meta.url),'utf8');
const dictionaries=vm.runInNewContext(source.slice(0,source.indexOf('let initialPageLoad'))+'; translations');
test('all languages cover every UI key and preserve placeholders',()=>{
 const keys=Object.keys(dictionaries.en).sort();
 for(const lang of ['kk','ru']) {
  assert.deepEqual(Object.keys(dictionaries[lang]).sort(),keys);
  for(const key of keys) {
   assert.ok(dictionaries[lang][key].trim(),`${lang}.${key}`);
   assert.deepEqual(dictionaries[lang][key].match(/\{\w+\}/g)||[],dictionaries.en[key].match(/\{\w+\}/g)||[]);
  }
 }
 for(const match of html.matchAll(/data-i18n(?:-aria)?="([^"]+)"/g)) assert.ok(dictionaries.kk[match[1]],match[1]);
 assert.ok(html.indexOf('id="lang-kk"')<html.indexOf('id="lang-ru"'));
 assert.ok(html.indexOf('id="lang-ru"')<html.indexOf('id="lang-en"'));
});
function context(search,saved) {
 const c={URLSearchParams,URL,window:{location:{search,href:'https://example.test/'+search},localStorage:{getItem:()=>saved},history:{replaceState:(_a,_b,u)=>{c.lastUrl=u;}},addEventListener:()=>{}}};
 vm.createContext(c);vm.runInContext(source.slice(0,source.indexOf('const elements =')),c);
 return c;
}
test('Kazakh URL overrides saved language and survives a shared device URL',()=>{
 const c=context('?lang=kk','en');
 assert.equal(vm.runInContext('state.language',c),'kk');
 const start=source.indexOf('function setUrl('),end=source.indexOf('\n}\n',start)+3;
 vm.runInContext(source.slice(start,end),c);
 vm.runInContext('setUrl("edge-77BD19", "batch-1")',c);
 assert.equal(c.lastUrl.searchParams.get('lang'),'kk');
 assert.equal(c.lastUrl.searchParams.get('device'),'edge-77BD19');
 assert.equal(c.lastUrl.searchParams.get('batch'),'batch-1');
});
test('saved Kazakh and existing preferences survive reload; invalid values fall back',()=>{
 for(const lang of ['kk','ru','en']) assert.equal(vm.runInContext('state.language',context('',lang)),lang);
 assert.equal(vm.runInContext('state.language',context('?lang=invalid','invalid')),'ru');
});
