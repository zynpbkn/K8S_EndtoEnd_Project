{{- define "akilli-sinif.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{- define "akilli-sinif.namespace" -}}
{{ .Values.global.namespace }}
{{- end }}
