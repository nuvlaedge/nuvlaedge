set -x

openssl genrsa -out ks-user.key 2048
openssl req -new -key ks-user.key -out ks-user.csr

BASE64_CSR=$(cat ./ks-user.csr | base64 | tr -d '\n')

cat > ks-csr.yaml << EOF
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: ks-user
spec:
  request: ${BASE64_CSR}
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: 86400  # one day
  usages:
  - client auth
EOF

kubectl apply -f ks-csr.yaml

exit

kubectl certificate approve ks-user

kubectl get csr ks-user -o jsonpath='{.status.certificate}'| base64 -d > ks-user.crt

openssl x509 -noout -modulus -in ks-user.crt | openssl md5
openssl rsa -noout -modulus -in ks-user.key | openssl md5

curl -f https://185.19.30.2:6443/api --cacert ./ca.crt --cert ./ks-user.crt --key ./ks-user.key