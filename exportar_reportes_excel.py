"""Exportación XLSX de una consulta ya realizada, sin dependencias adicionales."""
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,InvalidOperation
from io import BytesIO
from zipfile import ZipFile,ZIP_DEFLATED
from xml.etree.ElementTree import Element,SubElement,tostring
import math,re,unicodedata

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
CAMPOS={
 'solicitudes':[('Solicitud','solicitud'),('Obra','obra'),('Solicitante','solicitante'),('Artículo','articulo'),('Cantidad','cantidad'),('Proveedor','proveedor'),('Área','area'),('Estado','estado'),('Fecha','fecha'),('Observaciones','observaciones')],
 'compras':[('Planilla','planilla'),('Obra','obra'),('Solicitud','solicitud'),('Artículo','articulo'),('Cantidad','cantidad'),('Proveedor','proveedor'),('Estado','estado'),('Fecha','fecha'),('Observaciones','observaciones')],
 'entregas':[('Entrega','entrega'),('Solicitud','solicitud'),('Obra solicitante','obra'),('Artículo','articulo'),('Cantidad solicitada','cantidad'),('Entregada por','entregado_por'),('Fecha y hora','fecha'),('Observaciones','observaciones')],
 'obras':[('Obra','obra'),('Dirección','direccion'),('Contratistas','contratistas'),('Estado','activo')]
}
def texto(v):return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff]','',str(v))[:32767]
def columna(n):
 s=''
 while n:n,r=divmod(n-1,26);s=chr(65+r)+s
 return s
def convertir(v,encabezado):
 if v is None:return '',0
 if isinstance(v,bool):return ('Activa' if v else 'Inactiva'),0
 if 'fecha' in encabezado.casefold() and not isinstance(v,(datetime,date)):
  cadena=str(v).strip();valor=None
  try:valor=datetime.fromisoformat(cadena.replace('Z','+00:00')) if ('T' in cadena or ':' in cadena) else date.fromisoformat(cadena)
  except ValueError:
   for fmt in ('%d/%m/%Y %H:%M:%S','%d/%m/%Y %H:%M','%d/%m/%Y','%d-%m-%Y'):
    try:valor=datetime.strptime(cadena,fmt);break
    except ValueError:pass
  if valor is not None:v=valor
 if isinstance(v,(datetime,date)):
  if isinstance(v,date) and not isinstance(v,datetime):v=datetime.combine(v,datetime.min.time())
  if v.tzinfo:v=v.astimezone(timezone(timedelta(hours=-3))).replace(tzinfo=None)
  serial=(v-datetime(1899,12,30)).total_seconds()/86400
  return serial,4 if (v.hour or v.minute or v.second or 'hora' in encabezado.casefold()) else 3
 numerico=any(p in encabezado.casefold() for p in ('cantidad',)) or encabezado.casefold() in ('solicitud','planilla','entrega','id')
 if isinstance(v,(int,float,Decimal)) or numerico:
  try:
   n=Decimal(str(v));
   if n.is_finite():return n,2
  except InvalidOperation:pass
 return texto(v),0
def crear_excel(titulo,encabezados,filas,filtros=()):
 if not encabezados or len(encabezados)>100:raise ValueError('Encabezados inválidos.')
 if len(filas)>1_000_000:raise ValueError('La consulta supera el máximo de filas de Excel. Aplicá más filtros.')
 filtros=list(filtros);hoja=Element('worksheet',xmlns=NS)
 inicio=6+len(filtros);fin=inicio+len(filas);ultima=columna(len(encabezados))
 SubElement(hoja,'dimension',ref=f'A1:{ultima}{fin}')
 vistas=SubElement(hoja,'sheetViews');vista=SubElement(vistas,'sheetView',workbookViewId='0');SubElement(vista,'pane',ySplit=str(inicio),topLeftCell=f'A{inicio+1}',activePane='bottomLeft',state='frozen')
 cols=SubElement(hoja,'cols')
 for i,h in enumerate(encabezados,1):
  ancho=16 if any(p in h.casefold() for p in ('cantidad','fecha')) else 24
  if 'observaciones' in h.casefold():ancho=55
  SubElement(cols,'col',min=str(i),max=str(i),width=str(ancho),customWidth='1')
 datos=SubElement(hoja,'sheetData')
 def fila(numero,valores,estilo=None,solo_texto=False):
  row=SubElement(datos,'row',r=str(numero))
  for i,(valor,enc) in enumerate(zip(valores,encabezados),1):
   valor,s=(texto(valor),0) if solo_texto else convertir(valor,enc);s=estilo if estilo is not None else s
   cell=SubElement(row,'c',r=f'{columna(i)}{numero}',s=str(s))
   if isinstance(valor,(int,float,Decimal)):
    SubElement(cell,'v').text=str(valor)
   else:
    cell.set('t','inlineStr');SubElement(SubElement(cell,'is'),'t',{'{http://www.w3.org/XML/1998/namespace}space':'preserve'}).text=texto(valor)
 fila(1,[titulo],1,True)
 fila(2,['Exportado',datetime.now(timezone(timedelta(hours=-3))).strftime('%d/%m/%Y %H:%M')])
 fila(3,['Resultados',len(filas)])
 for n,(campo,valor) in enumerate(filtros,4):fila(n,[campo,str(valor)],solo_texto=True)
 fila(inicio,encabezados,5,True)
 for n,valores in enumerate(filas,inicio+1):fila(n,list(valores))
 SubElement(hoja,'autoFilter',ref=f'A{inicio}:{ultima}{fin}')
 merges=SubElement(hoja,'mergeCells',count='1');SubElement(merges,'mergeCell',ref=f'A1:{ultima}1')
 SubElement(hoja,'pageMargins',left='0.3',right='0.3',top='0.5',bottom='0.5',header='0.3',footer='0.3')
 estilos=f'''<styleSheet xmlns="{NS}"><numFmts count="3"><numFmt numFmtId="164" formatCode="#,##0.########"/><numFmt numFmtId="165" formatCode="dd/mm/yyyy"/><numFmt numFmtId="166" formatCode="dd/mm/yyyy hh:mm"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="12"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF223C61"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1"><alignment wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
 archivos={
 '[Content_Types].xml':'''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>''',
 '_rels/.rels':'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>''',
 'xl/workbook.xml':f'''<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Resultados" sheetId="1" r:id="rId1"/></sheets></workbook>''',
 'xl/_rels/workbook.xml.rels':'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>''',
 'xl/styles.xml':estilos,'xl/worksheets/sheet1.xml':tostring(hoja,encoding='utf-8',xml_declaration=True)}
 salida=BytesIO()
 with ZipFile(salida,'w',ZIP_DEFLATED) as z:
  for nombre,valor in archivos.items():z.writestr(nombre,valor)
 return salida.getvalue()

def instalar_boton(tabla,titulo,gestor='pack'):
    import tkinter as tk
    from tkinter import filedialog,messagebox
    def exportar():
        ids=tabla.get_children()
        if not ids:return messagebox.showinfo('Exportar Excel','Primero realizá una consulta con resultados.',parent=tabla.winfo_toplevel())
        columnas=list(tabla['columns']);encabezados=[tabla.heading(c,'text') for c in columnas]
        filas=[tabla.item(i,'values') for i in ids]
        ruta=filedialog.asksaveasfilename(parent=tabla.winfo_toplevel(),title='Guardar consulta como Excel',defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')],initialfile='100T_'+titulo.lower().replace(' ','_')+'.xlsx')
        if not ruta:return
        try:
            from pathlib import Path
            datos=crear_excel('100T · '+titulo,encabezados,filas,getattr(tabla,'_filtros_excel',[]));destino=Path(ruta)
            from tempfile import NamedTemporaryFile
            with NamedTemporaryFile(dir=destino.parent,suffix='.xlsx.tmp',delete=False) as f:
                temporal=Path(f.name)
                try:f.write(datos)
                except Exception:
                    f.close();temporal.unlink(missing_ok=True);raise
            try:temporal.replace(destino)
            finally:
                if temporal.exists():temporal.unlink()
            messagebox.showinfo('Excel guardado',f'Se exportaron {len(filas)} resultados.\n\n{ruta}',parent=tabla.winfo_toplevel())
        except Exception as e:messagebox.showerror('No se pudo exportar',str(e),parent=tabla.winfo_toplevel())
    boton=tk.Button(tabla.master,text='EXPORTAR A EXCEL',command=exportar,bg='#217346',fg='white',font=('Arial',10,'bold'),padx=12,pady=8)
    if gestor=='grid':boton.grid(row=2,column=0,columnspan=2,sticky='e',pady=5)
    else:boton.pack(side='bottom',anchor='e',pady=5)
