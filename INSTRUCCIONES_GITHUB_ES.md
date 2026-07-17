# Actualizar Agents Morf en GitHub sin romper `main`

Repositorio: `https://github.com/CodeMorf/agents-Morf.git`

No uses `--force` para esta actualización. Crea una rama de revisión:

```powershell
git checkout -b architecture-v0.2
git add .
git commit -m "Decouple product backends and add memory training platform"
git push -u origin architecture-v0.2
```

Después abre un Pull Request hacia `main`, revisa los cambios y espera que GitHub Actions termine correctamente.

La plataforma Agents Morf contiene la API, interfaz, agentes, memoria, RAG, herramientas, proveedores, ejemplos de entrenamiento, evaluaciones y feedback. Los motores de correo, WhatsApp, reservas, pagos, órdenes y calendarios permanecen en los backends de cada producto.

No subas `.env`, claves privadas, datos de clientes ni el ZIP/código fuente de Grok Build. Grok Build se mantiene independiente y solo puede conectarse mediante el adaptador restringido documentado.
