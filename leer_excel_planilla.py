"""Lector acotado XLSX para importar solicitudes. No ejecuta fórmulas ni macros."""
from io import BytesIO
from zipfile import ZipFile,BadZipFile
from xml.etree import ElementTree as ET
from decimal import Decimal,InvalidOperation
import posixpath,re,unicodedata

MAX_ARCHIVO=8*1024*1024
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
def normalizar(v):
    s=unicodedata.normalize('NFKD',str('' if v is None else v).replace('×','x')).casefold()
    return ''.join(c for c in s if c.isalnum() and not unicodedata.combining(c))
def unidad_clave(v):
    s=normalizar(v)
    for principal,variantes in {
      'u':('u','un','unidad','unidades','pieza','piezas'),
      'kg':('kg','kgs','kilo','kilos','kilogramo','kilogramos'),
      'l':('l','lt','lts','litro','litros'),
      'm2':('m2','metroscuadrados'), 'm3':('m3','metroscubicos'),
      'bolsa':('bolsa','bolsas'),'barra':('barra','barras'),'rollo':('rollo','rollos')}.items():
        if s in variantes:return principal
    return s
def cantidad(v):
    if v is None or isinstance(v,bool):raise ValueError('Falta una cantidad numérica.')
    s=str(v).strip().replace(' ','')
    if ',' in s and '.' in s:
        s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    else:s=s.replace(',','.')
    try:n=Decimal(s)
    except InvalidOperation:raise ValueError('Cantidad inválida: revisala o excluí esta fila.') from None
    if not n.is_finite() or n<=0 or n>Decimal('1000000000'):raise ValueError('La cantidad debe ser mayor que cero y menor o igual a 1.000.000.000.')
    return n
def letra(numero):
    s=''
    while numero:numero,r=divmod(numero-1,26);s=chr(65+r)+s
    return s
def indice(referencia):
    m=re.match(r'([A-Z]+)',referencia.upper());n=0
    if not m:raise ValueError('Referencia de celda inválida.')
    for c in m[1]:n=n*26+ord(c)-64
    return n
ALIAS={
 'cantidad':{'apedir':100,'cantidadapedir':100,'cantidad':80,'cant':80,'cantidades':70,'redondeo':30},
 'descripcion':{'descripcion':100,'descripc ion':100,'articulo':95,'material':90,'item':90,'producto':90,'detalle':70},
 'area':{'area':100,'areadeobra':95,'sector':80,'rubro':60},
 'unidad':{'unidad':100,'unidades':90,'unid':90,'um':80},
 'presentacion':{'presentacion':100,'formatodecompra':90},
 'observaciones':{'observaciones':100,'observacion':100,'notas':80}}

class Libro:
    def __init__(self,contenido):
        if not contenido or len(contenido)>MAX_ARCHIVO:raise ValueError('Elegí un archivo .xlsx de hasta 8 MB.')
        try:self.zip=ZipFile(BytesIO(contenido))
        except BadZipFile:raise ValueError('No es un Excel .xlsx válido. Si es .xls, guardalo como .xlsx.') from None
        infos=self.zip.infolist()
        if len(infos)>2500 or sum(i.file_size for i in infos)>50*1024*1024:raise ValueError('El Excel es demasiado grande al descomprimir. Copiá el pedido a un archivo más pequeño.')
        if any('vbaproject' in i.filename.lower() for i in infos):raise ValueError('Guardá una copia .xlsx sin macros para importar.')
        self.cadenas=[]
        if 'xl/sharedStrings.xml' in self.zip.namelist():
            self.cadenas=[''.join(t.text or '' for t in n.findall('.//m:t',NS)) for n in self.xml('xl/sharedStrings.xml').findall('m:si',NS)]
        relaciones={n.attrib['Id']:n for n in self.xml('xl/_rels/workbook.xml.rels')}
        self.hojas=[]
        for n in self.xml('xl/workbook.xml').findall('m:sheets/m:sheet',NS):
            rel=relaciones.get(n.attrib.get(REL))
            if rel is None or rel.attrib.get('TargetMode')=='External' or not rel.attrib.get('Type','').endswith('/worksheet'):continue
            target=rel.attrib['Target'];ruta=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl',target))
            if not ruta.startswith('xl/') or ruta not in self.zip.namelist():raise ValueError('La hoja tiene una ubicación inválida.')
            self.hojas.append({'nombre':n.attrib['name'],'ruta':ruta,'oculta':n.attrib.get('state','visible')!='visible'})
        if not self.hojas:raise ValueError('El archivo no tiene hojas de datos.')
    def xml(self,nombre):
        try:
            b=self.zip.read(nombre)
            if b'<!DOCTYPE' in b.upper() or b'<!ENTITY' in b.upper():raise ValueError('XML no permitido dentro del Excel.')
            return ET.fromstring(b)
        except (KeyError,ET.ParseError,RuntimeError):raise ValueError('No se pudo leer la estructura del Excel.') from None
    def filas(self,hoja):
        raiz=self.xml(hoja['ruta']);filas=[]
        for n in raiz.findall('m:sheetData/m:row',NS):
            nro=int(n.attrib.get('r',len(filas)+1))
            if nro>10000:raise ValueError('La hoja supera 10.000 filas. Separá el pedido en un archivo más pequeño.')
            celdas={}
            for c in n.findall('m:c',NS):
                col=indice(c.attrib.get('r','A1'))
                if col>150:raise ValueError('La hoja supera 150 columnas.')
                tipo=c.attrib.get('t','n');v=c.find('m:v',NS);v=v.text if v is not None else None
                if tipo=='s':
                    try:v=self.cadenas[int(v)]
                    except (ValueError,TypeError,IndexError):raise ValueError('Texto compartido inválido en el Excel.') from None
                elif tipo=='inlineStr':v=''.join(t.text or '' for t in c.findall('.//m:t',NS))
                elif tipo=='b':v=(v=='1')
                celdas[col]={'valor':v,'formula':c.find('m:f',NS) is not None,'tipo':tipo}
            filas.append((nro,celdas))
        return filas
    def leer(self,hoja=None,encabezado=None,columnas=None):
        seleccion=next((h for h in self.hojas if h['nombre']==hoja),None) if hoja else next((h for h in self.hojas if not h['oculta']),self.hojas[0])
        if seleccion is None:raise ValueError('La hoja seleccionada no existe.')
        datos=self.filas(seleccion);mejor=None
        for nro,celdas in datos[:100]:
            mapa={};puntaje=0
            for campo,alias in ALIAS.items():
                opciones=[(alias.get(normalizar(c['valor']),0),-col,col) for col,c in celdas.items()]
                if opciones:
                    p,_,col=max(opciones)
                    if p:mapa[campo]=col;puntaje+=p
            if 'cantidad' in mapa and 'descripcion' in mapa and (mejor is None or puntaje>mejor[0]):mejor=(puntaje,nro,mapa)
        if encabezado is None:
            if mejor is None:
                maxcol=max([max(c,default=0) for _,c in datos],default=1)
                return {'hojas':[{'nombre':h['nombre'],'oculta':h['oculta']} for h in self.hojas], 'hoja':seleccion['nombre'],'encabezado':1,'columnas':{},'opciones_columnas':[{'id':i,'nombre':letra(i)} for i in range(1,maxcol+1)],'filas':[],'avisos':['Indicá la fila de encabezados y las columnas Cantidad y Descripción para leer este archivo.']}
            encabezado=mejor[1]
        if encabezado<1 or encabezado>10000:raise ValueError('Fila de encabezados inválida.')
        cabecera=next((c for n,c in datos if n==encabezado),{})
        mapa=(mejor[2] if mejor and mejor[1]==encabezado else {}) if columnas is None else columnas
        if not all(mapa.get(k) for k in ('cantidad','descripcion')):raise ValueError('Seleccioná las columnas Cantidad y Descripción.')
        if any(type(v) is not int or v<0 or v>150 for v in mapa.values()):raise ValueError('Columnas inválidas.')
        if mapa['cantidad']==mapa['descripcion']:raise ValueError('Cantidad y Descripción deben ser columnas distintas.')
        salida=[];formulas=False
        for nro,celdas in datos:
            if nro<=encabezado:continue
            def celda(campo):return celdas.get(mapa.get(campo),{}).get('valor')
            desc=str(celda('descripcion') or '').strip();q=celda('cantidad')
            if not desc and (q is None or q==''):continue
            if normalizar(desc) in ALIAS['descripcion'] and normalizar(q) in ALIAS['cantidad']:continue
            if not desc:continue  # Títulos de sección y notas sin descripción de material.
            problemas=[]
            try:qtexto=str(cantidad(q));usar=True
            except ValueError as e:qtexto='' if q is None else str(q);problemas.append(str(e));usar=False
            c=celdas.get(mapa['cantidad'],{});formulas=formulas or c.get('formula',False)
            if c.get('formula') and q is None:problemas.append('La fórmula no tiene un resultado guardado. Abrí y guardá el Excel recalculado o escribí la cantidad.')
            obs=str(celda('observaciones') or '').strip();pres=str(celda('presentacion') or '').strip()
            if len(desc)>1000 or len(str(celda('unidad') or ''))>80 or len(obs)>1000 or len(pres)>1000 or len(str(celda('area') or ''))>500:raise ValueError(f'Fila {nro}: un texto es demasiado largo. Acortalo en el Excel antes de importar.')
            salida.append({'fila_excel':nro,'descripcion':desc[:1000],'cantidad':qtexto,'unidad':str(celda('unidad') or '').strip()[:80],'area_original':str('' if celda('area') is None else celda('area')).strip()[:500],'observaciones':obs[:1000],'presentacion':pres[:1000],'usar':usar,'problemas':problemas})
        if len(salida)>1000:raise ValueError('La hoja contiene más de 1.000 materiales. Dividí el pedido antes de importar.')
        if not salida:raise ValueError('No encontré materiales debajo de los encabezados seleccionados.')
        maxcol=max([max(c,default=0) for _,c in datos],default=1)
        return {'hojas':[{'nombre':h['nombre'],'oculta':h['oculta']} for h in self.hojas],'hoja':seleccion['nombre'],'encabezado':encabezado,'columnas':mapa,
          'opciones_columnas':[{'id':i,'nombre':f"{letra(i)} · {str(cabecera.get(i,{}).get('valor') or 'Sin título')[:70]}"} for i in range(1,maxcol+1)],
          'filas':salida,'avisos':['Se usan los resultados de las fórmulas guardados en el archivo; no se recalculan.'] if formulas else []}
