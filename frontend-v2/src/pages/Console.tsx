import { useState, useEffect } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ShieldAlert, Database, Link as LinkIcon, CheckCircle2, GitCommit, Network } from "lucide-react";

interface LogEntry {
  index: number;
  issuer_did: string;
  issuer_name: string;
  sebi_reg_no: string;
  artefact_type: string;
  title: string;
  timestamp: string;
  hash: string;
}

export default function Console() {
  const [sth, setSth] = useState<{ tree_size: number; root_hash: string } | null>(null);
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [proofData, setProofData] = useState<any>(null);
  const [isVerifying, setIsVerifying] = useState<number | null>(null);

  useEffect(() => {
    fetchData();
    // In a real dashboard, we'd poll or use websockets, but for demo, fetch once on mount.
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [sthRes, entriesRes] = await Promise.all([
        axios.get("/api/v1/log/sth"),
        axios.get("/api/v1/log/entries")
      ]);
      setSth(sthRes.data);
      setEntries(entriesRes.data.entries);
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    }
  };

  const generateProof = async (index: number) => {
    setIsVerifying(index);
    try {
      const res = await axios.get(`/api/v1/log/proof/${index}`);
      setProofData(res.data);
    } catch (error) {
      console.error(error);
      alert("Failed to fetch proof for index " + index);
    } finally {
      setIsVerifying(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-[#0B1B3A] text-white p-4 shadow-md flex justify-between items-center z-10">
        <div className="flex items-center gap-3">
          <Database className="w-6 h-6 text-[#E9B949]" />
          <div>
            <h1 className="font-serif font-bold text-lg">SEBI Regulator Console</h1>
            <p className="text-xs text-blue-200">PRAMAAN Transparency Log Monitor</p>
          </div>
        </div>
        {sth && (
          <div className="text-right">
            <div className="text-xs text-blue-200 uppercase tracking-wider font-semibold">Tree Size</div>
            <div className="font-mono text-xl font-bold text-[#00A870]">{sth.tree_size}</div>
          </div>
        )}
      </header>

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">
        
        {/* Hero STH */}
        {sth && (
          <Card className="bg-[#0B1B3A] text-white border-none shadow-lg">
            <CardContent className="p-6 flex flex-col md:flex-row gap-6 items-center justify-between">
              <div>
                <h2 className="text-sm uppercase tracking-wider text-blue-300 font-semibold mb-1 flex items-center gap-2">
                  <GitCommit className="w-4 h-4" /> Signed Tree Head (STH)
                </h2>
                <p className="font-mono text-lg md:text-2xl break-all text-[#E9B949] font-bold">
                  {sth.root_hash}
                </p>
              </div>
              <div className="shrink-0 text-center">
                <Badge variant="outline" className="border-[#00A870] text-[#00A870] bg-[#00A870]/10 px-4 py-1">
                  Cryptographically Anchored
                </Badge>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Log Table */}
          <Card className="lg:col-span-2 shadow-sm border-t-4 border-t-[#0B1B3A]">
            <CardHeader>
              <CardTitle className="font-serif">Global Transparency Log</CardTitle>
              <CardDescription>Append-only record of all official market communications.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader className="bg-gray-50">
                    <TableRow>
                      <TableHead className="w-[80px]">Index</TableHead>
                      <TableHead>Issuer</TableHead>
                      <TableHead>Title</TableHead>
                      <TableHead>Time</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((entry) => (
                      <TableRow key={entry.index}>
                        <TableCell className="font-mono font-medium">{entry.index}</TableCell>
                        <TableCell>
                          <div className="font-medium text-sm">{entry.issuer_name}</div>
                          <div className="text-xs text-gray-500">{entry.sebi_reg_no}</div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm font-medium">{entry.title}</div>
                          <Badge variant="secondary" className="text-[10px] mt-1">{entry.artefact_type}</Badge>
                        </TableCell>
                        <TableCell className="text-xs text-gray-500">
                          {new Date(entry.timestamp).toLocaleString()}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button 
                            variant="outline" 
                            size="sm"
                            onClick={() => generateProof(entry.index)}
                            disabled={isVerifying === entry.index}
                            className="text-xs"
                          >
                            {isVerifying === entry.index ? "Verifying..." : "Proof"}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                    {entries.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5} className="text-center py-6 text-gray-500">
                          No entries in the log yet.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Side Panel: Proof & Mock Visual */}
          <div className="space-y-6">
            {/* Proof View */}
            <Card className={`shadow-sm transition-all duration-500 ${proofData ? 'border-l-4 border-l-[#00A870]' : ''}`}>
              <CardHeader>
                <CardTitle className="font-serif text-base flex items-center gap-2">
                  <LinkIcon className="w-4 h-4" /> Inclusion Proof
                </CardTitle>
                <CardDescription className="text-xs">
                  Verify an entry belongs to the STH without trusting the log operator.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {proofData ? (
                  <div className="space-y-4 animate-in fade-in">
                    <div className="flex items-center justify-between bg-gray-50 p-3 rounded-lg border">
                      <span className="text-sm font-medium text-gray-700">Index #{proofData.index}</span>
                      {proofData.verified_locally ? (
                        <Badge className="bg-[#00A870] hover:bg-[#00A870] text-white">
                          <CheckCircle2 className="w-3 h-3 mr-1" /> Verified Locally
                        </Badge>
                      ) : (
                        <Badge variant="destructive">Verification Failed</Badge>
                      )}
                    </div>
                    
                    <div>
                      <div className="text-xs font-semibold text-gray-500 uppercase mb-2">Audit Path (Hashes)</div>
                      <div className="bg-[#0B1B3A] text-blue-300 font-mono text-[10px] p-3 rounded-lg space-y-2 overflow-x-auto">
                        {proofData.audit_path.length > 0 ? (
                          proofData.audit_path.map((hash: string, i: number) => (
                            <div key={i} className="flex gap-2">
                              <span className="text-blue-500">[{i}]</span> {hash}
                            </div>
                          ))
                        ) : (
                          <div className="text-gray-400 italic">No intermediate hashes needed (Tree size 1)</div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-gray-500 text-center py-8 italic bg-gray-50 rounded-md border border-dashed">
                    Select an entry from the log to generate a cryptographic proof.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Mock Fraud Pattern Dashboard */}
            <Card className="shadow-sm overflow-hidden">
              <div className="bg-[#D6353B] text-white px-4 py-2 flex items-center justify-between">
                <div className="font-serif font-semibold text-sm flex items-center gap-2">
                  <Network className="w-4 h-4" /> Fraud Campaign Correlation
                </div>
                <Badge variant="outline" className="text-white border-white/30 bg-white/10 text-[10px] uppercase">
                  Mock Data
                </Badge>
              </div>
              <CardContent className="p-0">
                <div className="p-4 bg-red-50/50 space-y-3">
                  <div className="text-xs text-red-800 bg-red-100 p-2 rounded-md border border-red-200">
                    <strong>Coming:</strong> live campaign correlation via Neo4j. The data below is synthetic for demonstration purposes.
                  </div>
                  
                  <div className="space-y-2 pt-2">
                    <div className="flex justify-between items-center text-sm">
                      <span className="font-medium text-gray-700">Cluster 4A (Telegram/WhatsApp)</span>
                      <span className="text-red-600 font-bold">142 Blocks</span>
                    </div>
                    <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
                      <div className="h-full bg-[#D6353B] w-[85%]"></div>
                    </div>
                    <p className="text-xs text-gray-500 leading-tight">
                      Identified 142 identical unsealed messages claiming "Guaranteed 40% returns". 
                      Cross-referenced to 3 unregistered domains.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

          </div>
        </div>
      </main>
    </div>
  );
}
