// Pure quest graph and eligibility helpers. Keep AND, OR and breadcrumbs separate.
const QuestAtlasModel = (() => {
  const prerequisites = q => [...new Set([...(q.all || []).map(Math.abs), ...(q.any || []),q.parentActive,q.availableStartingWith].filter(Boolean))];
  function prerequisitesMet(q, completed, lookup) {
    const all = (q.all || []).every(id => completed.has(Math.abs(id)) || (id > 0 && (lookup(id)?.exclusive || []).some(x => completed.has(x))));
    const any = !(q.any || []).length || q.any.some(id => completed.has(id));
    return all && any;
  }
  function ancestors(id, lookup) {
    const ordered = [], visiting = new Set(), seen = new Set(), cycles = [];
    function visit(i) {
      if (visiting.has(i)) { cycles.push(i); return; }
      if (seen.has(i)) return;
      visiting.add(i);
      const q = lookup(i);
      if (q) for (const pre of prerequisites(q)) visit(pre);
      visiting.delete(i); seen.add(i);
      if (i !== id) ordered.push(i);
    }
    visit(id);
    return { ids: ordered, cycles };
  }
  function filter(rows, f, zones, completed) {
    const search = (f.search || '').trim().toLocaleLowerCase();
    return rows.filter(q => {
      if (!f.indexOnly && !q.listed && !q.observed) return false;
      if (!f.indexOnly && q.placeholder) return false;
      if (f.side && q.side && q.side !== 3 && q.side !== +f.side) return false;
      if (f.zone && q.zone !== +f.zone) return false;
      if (f.dungeon && !(q.dungeons || []).includes(+f.dungeon)) return false;
      if (f.classMask && q.classMask && !(q.classMask & +f.classMask)) return false;
      if (f.min && q.level != null && q.level >= 0 && q.level < +f.min) return false;
      if (f.max && q.level != null && q.level >= 0 && q.level > +f.max) return false;
      if (f.kind === 'dungeon' && q.type !== 81 && !(q.dungeons || []).length) return false;
      if (f.kind === 'raid' && q.type !== 62) return false;
      if (f.kind === 'class' && !q.classMask) return false;
      if (f.kind === 'chain' && !q.hasChain) return false;
      if (f.kind === 'elite' && q.type !== 1) return false;
      if (f.change && q.change !== f.change) return false;
      if (f.hideDone && completed.has(q.id)) return false;
      if (search && !`${q.id} ${q.name} ${q.nameEn} ${q.search} ${zones[q.zone]?.name || ''}`.toLocaleLowerCase().includes(search)) return false;
      return true;
    }).sort((a,b) => (a.level>0?a.level:1000) - (b.level>0?b.level:1000) || a.id-b.id);
  }
  function validateProgress(input) {
    if (!input || input.schemaVersion !== 1 || (input.product && input.product !== 'wow_classic_beta') || !Array.isArray(input.completed) || input.completed.length > 20000 || input.completed.some(id => !Number.isSafeInteger(id) || id <= 0)) throw new Error('请选择本站导出的任务进度 JSON 文件。');
    return [...new Set(input.completed)];
  }
  return { prerequisites, prerequisitesMet, ancestors, filter, validateProgress };
})();
