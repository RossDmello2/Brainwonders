import{displayValue}from"./template-fields.js";
const token=/\{\{\s*([A-Z][A-Z0-9_]{0,47})\s*\}\}/g,rowToken=/\{\{\s*row\.([A-Z][A-Z0-9_]{0,47})\s*\}\}/g;
function alpha(n){let s="";while(n){n--;s=String.fromCharCode(65+n%26)+s;n=Math.floor(n/26)}return s}
function context(config,values){const root={};config.fields.forEach(f=>root[f.placeholder]=displayValue(f,values.fields[f.id]));return root}
function rowsFor(section,values){return values.sections[section.id].map((raw,index)=>{const r={};section.row_fields.forEach(f=>r[f.placeholder]=displayValue(f,raw[f.id]));if(section.numbering.style!=="none"){let n=section.numbering.start+index,label=section.numbering.style==="decimal"?String(n):alpha(n);if(section.numbering.style==="lower-alpha")label=label.toLowerCase();r[section.numbering.placeholder]=section.numbering.prefix+label+section.numbering.suffix}return r})}
const fill=(text,root,row={})=>text.replace(token,(_,k)=>root[k]??"").replace(rowToken,(_,k)=>row[k]??"");
export function renderPreview(target,config,values){
  target.replaceChildren();
  const root=context(config,values);
  target.lang=config.preview.language;
  target.dir=config.preview.direction;
  target.style.fontFamily=config.preview.font_family;
  target.style.fontSize=`${config.preview.font_size_pt}pt`;
  target.style.lineHeight=config.preview.line_height;
  config.preview.blocks.forEach(block=>{
    if(block.type==="paragraph"||block.type==="heading"){
      const el=document.createElement(block.type==="heading"?`h${block.level}`:"p");
      el.textContent=fill(block.text,root);
      el.style.textAlign=block.align;
      el.style.whiteSpace=block.preserve_newlines?"pre-wrap":"normal";
      target.append(el);
      return;
    }
    const section=config.sections.find(s=>s.placeholder===block.section);
    const rows=rowsFor(section,values);
    if(block.type==="repeat"){
      rows.forEach(row=>block.blocks.forEach(item=>{
        const paragraph=document.createElement("p");
        paragraph.textContent=fill(item.text,root,row);
        paragraph.style.textAlign=item.align;
        paragraph.style.whiteSpace=item.preserve_newlines?"pre-wrap":"normal";
        target.append(paragraph);
      }));
      return;
    }
    const table=document.createElement("table"),head=document.createElement("thead"),headerRow=document.createElement("tr");
    block.columns.forEach(column=>{
      const th=document.createElement("th");
      th.textContent=column.label;
      th.style.width=`${column.width_percent}%`;
      headerRow.append(th);
    });
    head.append(headerRow);
    table.append(head);
    const body=document.createElement("tbody");
    rows.forEach(row=>{
      const tr=document.createElement("tr");
      block.columns.forEach(column=>{
        const td=document.createElement("td");
        td.textContent=fill(column.text,root,row);
        tr.append(td);
      });
      body.append(tr);
    });
    table.append(body);
    target.append(table);
  });
  return fill(config.output.print_title_pattern,root);
}
