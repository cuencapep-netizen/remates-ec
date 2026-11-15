"""Minimal JSF/RichFaces client for remates.funcionjudicial.gob.ec (public search)."""
import re
import urllib.request
import urllib.parse
import http.cookiejar

BASE = "https://remates.funcionjudicial.gob.ec/rematesjudiciales-web"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


class RematesSession:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.op.addheaders = [("User-Agent", UA), ("Accept-Language", "es-EC,es;q=0.9")]
        self.url = BASE + "/pages/public/filtrando0.jsf"
        self.vs = None

    # ---------- low level ----------
    def _open(self, url, data=None, ajax=False, referer=None):
        h = {"Referer": referer or self.url}
        if data is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        if ajax:
            h["Faces-Request"] = "partial/ajax"
            h["X-Requested-With"] = "XMLHttpRequest"
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        r = self.op.open(urllib.request.Request(url, data=body, headers=h), timeout=90)
        raw = r.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", "replace")
        return r.geturl(), text

    def get(self, url=None, update_vs=True):
        url = url or self.url
        final, html = self._open(url)
        if update_vs:
            m = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
            if m:
                self.vs = m.group(1)
        return final, html

    def post(self, data, ajax=True):
        return self._open(self.url, data, ajax=ajax)

    # ---------- helpers ----------
    @staticmethod
    def updates(xml):
        return dict(re.findall(r'<update id="([^"]+)"><!\[CDATA\[(.*?)\]\]></update>', xml, re.S))

    @staticmethod
    def redirect(xml):
        m = re.search(r'<redirect url="([^"]+)"', xml)
        return m.group(1) if m else None

    def _absorb(self, xml):
        u = self.updates(xml)
        if "javax.faces.ViewState" in u:
            self.vs = u["javax.faces.ViewState"].strip()
        return u

    # ---------- flow ----------
    def accept_terms(self):
        url = BASE + "/pages/public/portal.jsf"
        final, html = self.get(url)
        form = re.search(r'<form id="([^"]+)" name="\1"', html).group(1)
        self.post({
            "javax.faces.partial.ajax": "true", "javax.faces.source": "pagoDiferido",
            "javax.faces.partial.execute": "pagoDiferido", "javax.faces.partial.render": "panelBoton",
            "javax.faces.behavior.event": "change", "javax.faces.partial.event": "change",
            form: form, "pagoDiferido": "on", "javax.faces.ViewState": self.vs})
        final, html = self.get(url)
        _, resp = self.post({
            "javax.faces.partial.ajax": "true", "javax.faces.source": "btn_aceptar_solicitud2",
            "javax.faces.partial.execute": "@all", "javax.faces.partial.render": "@all",
            "javax.faces.behavior.event": "click", "javax.faces.partial.event": "click",
            "org.richfaces.ajax.component": "btn_aceptar_solicitud2",
            form: form, "pagoDiferido": "on",
            "btn_aceptar_solicitud2": "btn_aceptar_solicitud2",
            "javax.faces.ViewState": self.vs})
        self.vs = None
        self.get()
        return True

    def click(self, source, render="pnlF", execute="@all", extra=None, opt_select="INICIO"):
        data = {
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": source,
            "javax.faces.partial.execute": execute,
            "javax.faces.partial.render": render,
            "javax.faces.behavior.event": "click",
            "javax.faces.partial.event": "click",
            "org.richfaces.ajax.component": source,
            "formFiltrado": "formFiltrado",
            "optSelect": opt_select,
            source: source,
            "javax.faces.ViewState": self.vs,
        }
        if extra:
            data.update(extra)
        _, resp = self.post(data)
        return resp, self._absorb(resp)
